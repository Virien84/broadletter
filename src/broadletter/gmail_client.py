"""Gmail access. The only module that talks to Google.

Scope: gmail.modify. It is the narrowest scope that can label, trash and insert the
broadcast into the inbox. Caveat: it would also allow sending mail, so this module
exposes NO send function and the LLM never gets tools (see CLAUDE.md).
"""

from __future__ import annotations

import base64
import email
import email.policy
from collections import Counter
from collections.abc import Iterator
from email.message import EmailMessage
from email.utils import parseaddr

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build

from broadletter.config import CREDENTIALS_PATH, TOKEN_PATH

SCOPES = ["https://www.googleapis.com/auth/gmail.modify"]


def authorize(interactive: bool = False) -> Credentials:
    creds = None
    if TOKEN_PATH.exists():
        creds = Credentials.from_authorized_user_file(str(TOKEN_PATH), SCOPES)
    if creds and creds.valid:
        return creds
    if creds and creds.expired and creds.refresh_token:
        creds.refresh(Request())
    elif interactive:
        if not CREDENTIALS_PATH.exists():
            raise FileNotFoundError(
                f"Missing {CREDENTIALS_PATH}. Download it from Google Cloud "
                "(OAuth client of type 'Desktop app')."
            )
        flow = InstalledAppFlow.from_client_secrets_file(str(CREDENTIALS_PATH), SCOPES)
        creds = flow.run_local_server(port=0, open_browser=True)
    else:
        raise RuntimeError("No valid token. Run first: broadletter auth")
    TOKEN_PATH.parent.mkdir(parents=True, exist_ok=True)
    TOKEN_PATH.write_text(creds.to_json(), encoding="utf-8")
    return creds


class Gmail:
    def __init__(self, creds: Credentials):
        self._svc = build("gmail", "v1", credentials=creds, cache_discovery=False)
        self._labels: dict[str, str] | None = None

    def my_address(self) -> str:
        return self._svc.users().getProfile(userId="me").execute()["emailAddress"]

    # --- labels ----------------------------------------------------------------------

    def label_id(self, name: str, create: bool = False) -> str | None:
        if self._labels is None:
            resp = self._svc.users().labels().list(userId="me").execute()
            self._labels = {lb["name"]: lb["id"] for lb in resp.get("labels", [])}
        if name not in self._labels and create:
            created = self._svc.users().labels().create(userId="me", body={"name": name}).execute()
            self._labels[name] = created["id"]
        return self._labels.get(name)

    # --- reading ---------------------------------------------------------------------

    def list_message_ids(self, label_id: str, limit: int, query: str | None = None) -> list[str]:
        ids: list[str] = []
        page_token = None
        while len(ids) < limit:
            resp = (
                self._svc.users()
                .messages()
                .list(userId="me", labelIds=[label_id], q=query,
                      maxResults=min(100, limit - len(ids)), pageToken=page_token)
                .execute()
            )
            ids += [m["id"] for m in resp.get("messages", [])]
            page_token = resp.get("nextPageToken")
            if not page_token:
                break
        return ids[:limit]

    def get_message(self, message_id: str) -> EmailMessage:
        resp = self._svc.users().messages().get(userId="me", id=message_id, format="raw").execute()
        raw = base64.urlsafe_b64decode(resp["raw"])
        return email.message_from_bytes(raw, policy=email.policy.default)  # type: ignore[return-value]

    def suggest_newsletter_senders(self, sample: int = 200) -> list[tuple[str, int]]:
        """Inbox senders that carry a List-Unsubscribe header. Read-only, suggestions only."""
        resp = (
            self._svc.users()
            .messages()
            .list(userId="me", labelIds=["INBOX"], maxResults=min(sample, 500))
            .execute()
        )
        counts: Counter[str] = Counter()
        for m in resp.get("messages", []):
            meta = (
                self._svc.users()
                .messages()
                .get(userId="me", id=m["id"], format="metadata",
                     metadataHeaders=["From", "List-Unsubscribe"])
                .execute()
            )
            headers = {h["name"].lower(): h["value"] for h in meta["payload"].get("headers", [])}
            if "list-unsubscribe" in headers:
                counts[parseaddr(headers.get("from", ""))[1].lower()] += 1
        return counts.most_common()

    # --- writing (only these three operations, nothing else) --------------------------

    def insert_into_inbox(self, msg: EmailMessage) -> str:
        """Places a message in the inbox WITHOUT sending it: it never leaves the account."""
        raw = base64.urlsafe_b64encode(msg.as_bytes()).decode()
        resp = (
            self._svc.users()
            .messages()
            .insert(userId="me", body={"raw": raw, "labelIds": ["INBOX", "UNREAD"]},
                    internalDateSource="dateHeader")
            .execute()
        )
        return resp["id"]

    def add_label(self, message_id: str, label_id: str) -> None:
        self._svc.users().messages().modify(
            userId="me", id=message_id, body={"addLabelIds": [label_id]}
        ).execute()

    def trash(self, message_id: str) -> None:
        """Trash, never permanent deletion: recoverable for 30 days."""
        self._svc.users().messages().trash(userId="me", id=message_id).execute()


def age_queries(max_age_days: int) -> tuple[str, str]:
    """Gmail search queries splitting messages into (fresh, expired) at max_age_days."""
    if max_age_days < 1:
        raise ValueError("max_age_days must be at least 1")
    return f"newer_than:{max_age_days}d", f"older_than:{max_age_days}d"


def iter_messages(gmail: Gmail, ids: list[str]) -> Iterator[tuple[str, EmailMessage]]:
    for message_id in ids:
        yield message_id, gmail.get_message(message_id)
