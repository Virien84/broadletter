# Broadletter 🦥

**Your newsletters, read to you as one news broadcast. Locally.**

Broadletter reads the newsletters piling up in your Gmail and turns them into a single,
lighthearted two-host news broadcast (with anchors Maya and Leo). It merges stories that
several newsletters repeat and drops sponsored content. The broadcast lands in your inbox
and the originals go to the trash. Everything runs on your own machine with open-weight
models.

Built for the [Hacktoberfest Open-Source AI Challenge: Week 3 — "Slow and Steady"](https://dev.to/challenges/hacktoberfest-week3-2026-10-19).

> **Status:** early MVP. The local AI pipeline works end to end on sample newsletters.
> The Gmail integration is implemented, but it has not been tested yet against a real inbox.

## Why

Newsletters are mostly a roundup of links to other sites. I don't want to delete them
unread, I don't want them clogging my inbox, and two of them often tell me the same
story. Broadletter does the reading so I don't have to.

## Why open-weight, local models

- **Your email stays on your PC.** Newsletter content is only ever sent to a model running
  on `localhost`. The config refuses any remote model host.
- **No per-token bill.** Set it up once and it runs every night for free.
- **Swappable.** Any model Ollama can run works. A smaller model is faster, a bigger one
  writes better.

## How it works

```
Gmail label "Newsletter"
  → MIME to clean text (hidden text, scripts and URLs stripped)
  → Gemma 4 extracts each story as JSON and flags sponsored ones
  → sponsored stories dropped
  → EmbeddingGemma + cosine clustering merges duplicate stories
  → Gemma 4 writes the two-host script
  → broadcast inserted into your inbox (not sent)
  → originals labeled "Broadletter/Digested" and moved to trash
```

Newsletters from senders you mark as personal skip the AI entirely. They are listed in a
**"Letters to the Editor"** section instead.

## Security by design

- **The model has no tools.** It can only return JSON that matches a Pydantic schema. The
  code decides every action, so a newsletter with a prompt injection can at worst produce
  an odd summary. It can never act on your mailbox.
- **Untrusted input is sanitized and fenced.** Hidden HTML (a common injection vector),
  scripts and every URL are removed. The remaining text is wrapped in delimiters that the
  prompt says to treat as data.
- **Links are never followed.** Following them would fire trackers and could trigger
  "one-click unsubscribe" links.
- **There is no send function.** The broadcast reaches your inbox through
  `messages.insert`, which places the message without sending it.
- **Nothing is permanently deleted.** Newsletters go to the trash, where they stay
  recoverable for 30 days. Only the ones included in the broadcast are moved, and each move
  is logged to `data/audit.jsonl`.
- **Dry run by default.** Nothing changes in Gmail unless you pass `--apply`.

## Requirements

- Python 3.12 or later and [uv](https://docs.astral.sh/uv/)
- [Ollama](https://ollama.com) 0.40.6 or later
- A Gmail account and a Google Cloud project with the Gmail API enabled

## Setup

1. **Models**
   ```bash
   ollama pull gemma4:e4b-it-qat
   ollama pull embeddinggemma:300m
   ```
2. **Install**
   ```bash
   uv sync
   cp config.example.toml config.toml   # then edit it
   uv run broadletter check
   ```
3. **Gmail access**
   - In Google Cloud, enable the Gmail API.
   - Create an OAuth client of type **Desktop app**.
   - Save the client JSON as `secrets/credentials.json`.
   - Publish the OAuth consent screen to **Production**. In Testing mode, refresh tokens
     expire after 7 days. Google will warn that the app is unverified; that is expected
     for a personal app.
   - Then authorize:
     ```bash
     uv run broadletter auth
     ```
4. **Label your newsletters.** Create a Gmail filter that applies the `Newsletter` label.
   To find candidates:
   ```bash
   uv run broadletter senders
   ```

## Usage

```bash
uv run broadletter run --limit 5   # dry run: preview saved to data/, Gmail untouched
uv run broadletter run --apply     # insert the broadcast and trash the digested newsletters
```

Settings live in `config.toml`: label names, personal senders, models, GPU layers
(`num_gpu`), dedupe threshold, host names and output language.

## Development

```bash
uv run pytest -q
```

## Roadmap

- Merged summaries when several newsletters cover the same story
- Scheduled nightly run
- Two-voice audio with an open-weight TTS model (Kokoro)
- Optional Telegram delivery
- Reading linked articles safely (domain allowlist, no unsubscribe links)

## License

[MIT](LICENSE)
