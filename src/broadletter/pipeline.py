"""Orchestration: Gmail -> text -> stories -> dedupe -> script -> inbox -> trash.

Defaults to a dry run: it writes the preview to data/ and leaves the mailbox alone.
Only with apply=True does it insert the broadcast and trash newsletters, and only
the newsletters that made it into that broadcast, plus expired ones.

Newsletters max_age_days old or older are expired: they are never downloaded or sent
to the LLM, just labeled and trashed unread.
"""

from __future__ import annotations

import json
import logging
from datetime import date, datetime
from pathlib import Path

from broadletter.config import DATA_DIR, Config
from broadletter.dedupe import embedding_text, to_stories
from broadletter.digest import extract_items, group_related, render_email, write_script
from broadletter.extract import to_newsletter
from broadletter.gmail_client import Gmail, age_queries, authorize, iter_messages
from broadletter.llm import LocalLLM
from broadletter.models import Digest, Newsletter, NewsItem

log = logging.getLogger(__name__)


def run(cfg: Config, apply: bool = False, limit: int | None = None) -> Path | None:
    llm = LocalLLM(cfg.ollama)
    if missing := llm.missing_models():
        raise RuntimeError(f"Missing Ollama models: {', '.join(missing)} (use 'ollama pull')")

    gmail = Gmail(authorize())
    label_id = gmail.label_id(cfg.gmail.label)
    if label_id is None:
        raise RuntimeError(f"Gmail label '{cfg.gmail.label}' does not exist")

    fresh_query, expired_query = age_queries(cfg.gmail.max_age_days)
    fresh_ids = gmail.list_message_ids(label_id, limit or cfg.gmail.max_messages, fresh_query)
    expired_ids = gmail.list_message_ids(label_id, cfg.gmail.max_expired, expired_query)
    if not fresh_ids and not expired_ids:
        log.info("No pending newsletters. Back to sleep. 🦥")
        return None

    preview = _broadcast(cfg, llm, gmail, fresh_ids, apply) if fresh_ids else None
    if expired_ids:
        _discard_expired(cfg, gmail, expired_ids, apply)
    return preview


def _broadcast(cfg: Config, llm: LocalLLM, gmail: Gmail, ids: list[str], apply: bool) -> Path:
    newsletters: list[Newsletter] = []
    for message_id, msg in iter_messages(gmail, ids):
        newsletters.append(
            to_newsletter(message_id, msg, cfg.ollama.max_chars, cfg.gmail.personal_senders)
        )
    letters = [nl for nl in newsletters if nl.is_personal]
    news_sources = [nl for nl in newsletters if not nl.is_personal]

    items: list[NewsItem] = []
    included: list[str] = [nl.message_id for nl in letters]
    for nl in news_sources:
        try:
            extracted = extract_items(llm, nl, cfg.digest.language)
        except Exception:
            # A newsletter that fails stays in the inbox for the next run.
            log.exception("Could not process '%s' (%s)", nl.subject, nl.sender)
            continue
        included.append(nl.message_id)
        kept = [it for it in extracted if not it.sponsored and not it.job_posting]
        log.info("%s: %d stories (%d sponsored, %d job postings dropped)", nl.sender, len(kept),
                 sum(it.sponsored for it in extracted),
                 sum(it.job_posting and not it.sponsored for it in extracted))
        items += kept

    vectors = llm.embed([embedding_text(it) for it in items])
    stories = to_stories(items, vectors, cfg.digest.dedupe_threshold)
    log.info("%d items -> %d stories after deduplication", len(items), len(stories))
    try:
        stories = group_related(llm, stories)
    except Exception:
        # Grouping is a nicety: without it the broadcast is still complete.
        log.exception("Could not group related stories")
    log.info("%d segments after grouping related stories", len(stories))

    script = write_script(llm, stories, cfg.digest) if stories else None
    digest = Digest(
        title=cfg.digest.title,
        date=date.today().isoformat(),
        lines=script.lines if script else [],
        letters=letters,
        stories=stories,
    )
    preview = _save_preview(digest)

    if not apply:
        log.info("Dry run: preview at %s. Nothing was changed in Gmail.", preview)
        return preview

    msg = render_email(digest, gmail.my_address())
    gmail.insert_into_inbox(msg)
    processed_id = gmail.label_id(cfg.gmail.processed_label, create=True)
    for message_id in included:
        gmail.add_label(message_id, processed_id)
        gmail.trash(message_id)
    _append_audit("digested", included, preview.name)
    log.info("Broadcast is in your inbox. %d newsletters moved to trash.", len(included))
    return preview


def _discard_expired(cfg: Config, gmail: Gmail, ids: list[str], apply: bool) -> None:
    days = cfg.gmail.max_age_days
    if not apply:
        log.info("Dry run: %d newsletters %d+ days old would be discarded unread.", len(ids), days)
        return
    expired_id = gmail.label_id(cfg.gmail.expired_label, create=True)
    for message_id in ids:
        gmail.add_label(message_id, expired_id)
        gmail.trash(message_id)
    _append_audit("expired", ids, None)
    log.info("%d newsletters %d+ days old discarded unread (moved to trash).", len(ids), days)


def _save_preview(digest: Digest) -> Path:
    DATA_DIR.mkdir(exist_ok=True)
    path = DATA_DIR / f"broadcast-{datetime.now():%Y%m%d-%H%M%S}.json"
    path.write_text(digest.model_dump_json(indent=2), encoding="utf-8")
    return path


def _append_audit(reason: str, message_ids: list[str], digest_name: str | None) -> None:
    # Local log of what was trashed and why, so it can be recovered if needed.
    entry = {"at": datetime.now().isoformat(), "reason": reason, "trashed": message_ids,
             "digest": digest_name}
    DATA_DIR.mkdir(exist_ok=True)
    with (DATA_DIR / "audit.jsonl").open("a", encoding="utf-8") as f:
        f.write(json.dumps(entry) + "\n")
