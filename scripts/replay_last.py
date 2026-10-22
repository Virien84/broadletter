"""Replays the last digested newsletters through the current pipeline, read-only.

Fetches them from the trash by the ids in data/audit.jsonl and changes nothing in Gmail.
Usage: uv run python scripts/replay_last.py data/replay.json
"""
import json, logging, sys
from broadletter.config import load_config
from broadletter.dedupe import embedding_text, to_stories
from broadletter.digest import extract_items, group_related, write_script
from broadletter.extract import to_newsletter
from broadletter.gmail_client import Gmail, authorize, iter_messages
from broadletter.llm import LocalLLM

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
logging.getLogger("httpx").setLevel(logging.WARNING)
cfg = load_config(); llm = LocalLLM(cfg.ollama); gmail = Gmail(authorize())
audit = [json.loads(l) for l in open("data/audit.jsonl", encoding="utf-8")]
ids = [a for a in audit if a["reason"] == "digested"][-1]["trashed"]
items = []
for mid, msg in iter_messages(gmail, ids):
    nl = to_newsletter(mid, msg, cfg.ollama.max_chars, cfg.gmail.personal_senders)
    ex = extract_items(llm, nl, cfg.digest.language)
    for it in ex:
        if it.sponsored or it.job_posting:
            logging.info("  dropped (%s): %s", "sponsored" if it.sponsored else "job", it.title)
    kept = [it for it in ex if not it.sponsored and not it.job_posting]
    logging.info("%s: %d kept of %d", nl.sender, len(kept), len(ex))
    items += kept
stories = to_stories(items, llm.embed([embedding_text(it) for it in items]), cfg.digest.dedupe_threshold)
logging.info("%d items -> %d stories", len(items), len(stories))
stories = group_related(llm, stories)
logging.info("%d segments", len(stories))
script = write_script(llm, stories, cfg.digest)
out = sys.argv[1]
json.dump({"stories": [s.model_dump() for s in stories], "lines": [l.model_dump() for l in script.lines]},
          open(out, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
logging.info("saved %s", out)
