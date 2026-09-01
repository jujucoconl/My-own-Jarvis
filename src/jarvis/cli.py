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


def cmd_wardrobe_add(args: argparse.Namespace) -> int:
    from jarvis import wardrobe

    config = load_config(Path(args.config) if args.config else None)

    manual = None
    if args.manual:
        if not args.category:
            print("error: --manual requires --category", file=sys.stderr)
            return 1
        manual = {
            "category": args.category,
            "subtype": args.subtype or "",
            "primary_color": args.color or "",
            "secondary_colors": [],
            "warmth": args.warmth if args.warmth is not None else 3,
            "formality": args.formality or "casual",
            "rain_ok": args.rain_ok,
            "style_tags": [],
            "description": "",
        }

    item = wardrobe.add_item(
        Path(args.image),
        config.secrets.anthropic_api_key,
        config.secrets.anthropic_model,
        manual=manual,
        note=args.note,
    )
    print(f"Added {item.item_id}: {item.category}/{item.subtype} - {item.primary_color}, {item.formality}")
    return 0


def cmd_wardrobe_list(args: argparse.Namespace) -> int:
    from jarvis import wardrobe

    items = wardrobe.load_wardrobe()
    if not items:
        print("No wardrobe items yet. Add one with `jarvis wardrobe add <photo>`.")
        return 0
    for it in items:
        print(
            f"{it.item_id}  {it.category:<10} {it.subtype:<25} {it.primary_color:<12} "
            f"warmth={it.warmth} {it.formality}"
        )
    return 0


def cmd_wardrobe_remove(args: argparse.Namespace) -> int:
    from jarvis import wardrobe

    if wardrobe.remove_item(args.item_id):
        print(f"Removed {args.item_id}")
        return 0
    print(f"error: no wardrobe item with id {args.item_id}", file=sys.stderr)
    return 1


def cmd_wardrobe_style(args: argparse.Namespace) -> int:
    from jarvis import wardrobe

    config = load_config(Path(args.config) if args.config else None)
    items = wardrobe.load_wardrobe()
    profile = wardrobe.build_style_profile(
        items, config.user.style_notes, config.secrets.anthropic_api_key, config.secrets.anthropic_model
    )
    print(profile.summary)
    return 0


def cmd_wardrobe_gaps(args: argparse.Namespace) -> int:
    from jarvis import wardrobe

    config = load_config(Path(args.config) if args.config else None)
    items = wardrobe.load_wardrobe()
    profile = wardrobe.load_style_profile()
    gaps = wardrobe.find_wardrobe_gaps(
        items, profile, config.user.style_notes, config.secrets.anthropic_api_key, config.secrets.anthropic_model
    )
    for g in gaps:
        print(f"- {g}")
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

    wardrobe_parser = subparsers.add_parser("wardrobe", help="Manage your wardrobe and style profile.")
    wardrobe_sub = wardrobe_parser.add_subparsers(dest="wardrobe_command", required=True)

    add = wardrobe_sub.add_parser("add", help="Add a clothing item from a photo.")
    add.add_argument("image", help="Path to a photo of the item.")
    add.add_argument("--config", help="Path to config/user.yaml (default: config/user.yaml)")
    add.add_argument("--note", help="Optional note to help tag it (e.g. 'this runs small').")
    add.add_argument("--manual", action="store_true", help="Skip AI tagging and set fields yourself.")
    add.add_argument("--category", choices=["top", "bottom", "outerwear", "dress", "shoes", "accessory"])
    add.add_argument("--subtype", help="e.g. 'flannel button-up'")
    add.add_argument("--color", help="Primary color.")
    add.add_argument("--warmth", type=int, choices=range(1, 6))
    add.add_argument("--formality", choices=["casual", "smart_casual", "formal", "athletic"])
    add.add_argument("--rain-ok", action="store_true", dest="rain_ok")
    add.set_defaults(func=cmd_wardrobe_add)

    listp = wardrobe_sub.add_parser("list", help="List your wardrobe items.")
    listp.set_defaults(func=cmd_wardrobe_list)

    remove = wardrobe_sub.add_parser("remove", help="Remove a wardrobe item by id.")
    remove.add_argument("item_id")
    remove.set_defaults(func=cmd_wardrobe_remove)

    style = wardrobe_sub.add_parser("style", help="(Re)generate your style profile from your wardrobe.")
    style.add_argument("--config", help="Path to config/user.yaml (default: config/user.yaml)")
    style.set_defaults(func=cmd_wardrobe_style)

    gaps = wardrobe_sub.add_parser("gaps", help="Suggest missing pieces worth adding to your wardrobe.")
    gaps.add_argument("--config", help="Path to config/user.yaml (default: config/user.yaml)")
    gaps.set_defaults(func=cmd_wardrobe_gaps)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        return args.func(args)
    except (FileNotFoundError, RuntimeError, ValueError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
