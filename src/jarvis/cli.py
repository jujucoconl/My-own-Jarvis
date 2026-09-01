"""Command-line entrypoint: `jarvis brief`."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from rich.console import Console
from rich.markdown import Markdown

from jarvis.briefing import build_briefing
from jarvis.config import load_config
from jarvis.render import render_markdown


def _create_drafts(config, briefing) -> list[str]:
    """Opt-in: writes the AI-drafted replies as real drafts in Gmail/Outlook."""
    from jarvis.calendar_google import get_google_credentials
    from jarvis.email_gmail import create_gmail_draft
    from jarvis.email_outlook import create_outlook_draft_reply, get_outlook_token

    notes: list[str] = []
    google_creds = None
    ms_token = None

    for triage in briefing.important_emails:
        if not triage.draft_reply:
            continue
        email = triage.email
        try:
            if email.provider == "gmail":
                if google_creds is None:
                    google_creds = get_google_credentials(
                        config.secrets.google_credentials_path,
                        config.secrets.google_token_path,
                    )
                subject = email.subject
                if not subject.lower().startswith("re:"):
                    subject = f"Re: {subject}"
                create_gmail_draft(
                    google_creds, email.sender_email, subject, triage.draft_reply
                )
                notes.append(f"Drafted Gmail reply to {email.sender_email}: {email.subject}")
            elif email.provider == "outlook":
                if ms_token is None:
                    ms_token = get_outlook_token(
                        config.secrets.ms_client_id,
                        config.secrets.ms_tenant_id,
                        config.secrets.ms_token_cache_path,
                    )
                create_outlook_draft_reply(ms_token, email.message_id, triage.draft_reply)
                notes.append(f"Drafted Outlook reply to {email.sender_email}: {email.subject}")
        except Exception as exc:  # noqa: BLE001
            notes.append(f"Failed to draft reply to {email.sender_email}: {exc}")

    return notes


def cmd_brief(args: argparse.Namespace) -> int:
    console = Console()
    config = load_config(Path(args.config) if args.config else None)

    with console.status("[bold cyan]Gathering your morning briefing..."):
        briefing = build_briefing(config)

    if args.create_drafts:
        notes = _create_drafts(config, briefing)
        for n in notes:
            console.print(f"[green]:heavy_check_mark:[/] {n}")

    markdown_text = render_markdown(briefing)

    if args.output:
        Path(args.output).write_text(markdown_text)
        console.print(f"[green]Saved briefing to {args.output}[/]")
    else:
        console.print(Markdown(markdown_text))

    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="jarvis", description="Your personal morning briefing.")
    subparsers = parser.add_subparsers(dest="command", required=True)

    brief = subparsers.add_parser("brief", help="Generate today's briefing.")
    brief.add_argument("--config", help="Path to config/user.yaml (default: config/user.yaml)")
    brief.add_argument("--output", help="Write the briefing to this file instead of the terminal.")
    brief.add_argument(
        "--create-drafts",
        action="store_true",
        help="Also save the AI-drafted replies as real drafts in Gmail/Outlook.",
    )
    brief.set_defaults(func=cmd_brief)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        return args.func(args)
    except FileNotFoundError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
