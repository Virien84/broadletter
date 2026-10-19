"""Command line: broadletter {auth,check,senders,run}."""

from __future__ import annotations

import argparse
import logging

from broadletter.config import load_config


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="broadletter", description="Broadletter 🦥")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("auth", help="Authorize Gmail access (opens the browser)")
    sub.add_parser("check", help="Check Ollama and the configured models")
    senders = sub.add_parser("senders", help="Suggest senders that look like newsletters")
    senders.add_argument("--sample", type=int, default=200)
    run = sub.add_parser("run", help="Build the broadcast (dry run by default)")
    run.add_argument("--apply", action="store_true",
                     help="Insert the broadcast into Gmail and move newsletters to trash")
    run.add_argument("--limit", type=int, help="Maximum number of newsletters to process")
    args = parser.parse_args(argv)

    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    cfg = load_config()

    if args.command == "auth":
        from broadletter.gmail_client import authorize

        authorize(interactive=True)
        print("Authorized. Token saved to secrets/token.json")
    elif args.command == "check":
        from broadletter.llm import LocalLLM

        missing = LocalLLM(cfg.ollama).missing_models()
        if missing:
            print("Missing models:", ", ".join(missing))
            return 1
        print(f"OK: {cfg.ollama.chat_model} and {cfg.ollama.embed_model} are available")
    elif args.command == "senders":
        from broadletter.gmail_client import Gmail, authorize

        for addr, count in Gmail(authorize()).suggest_newsletter_senders(args.sample):
            print(f"{count:4d}  {addr}")
    elif args.command == "run":
        from broadletter.pipeline import run as run_pipeline

        run_pipeline(cfg, apply=args.apply, limit=args.limit)
    return 0
