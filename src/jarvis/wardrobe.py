"""Your actual clothes: photo -> tagged item, a derived style profile, and gap-finding.

Storage lives under wardrobe/ (images/, items.json, style_profile.json) - all
gitignored since it's personal data, created on first `jarvis wardrobe add`.
"""

from __future__ import annotations

import base64
import json
import uuid
from dataclasses import asdict
from datetime import datetime
from pathlib import Path

from anthropic import Anthropic

from jarvis.ai_json import parse_json_array, parse_json_object
from jarvis.config import REPO_ROOT
from jarvis.models import StyleProfile, WardrobeItem

WARDROBE_DIR = REPO_ROOT / "wardrobe"
IMAGES_DIR = WARDROBE_DIR / "images"
ITEMS_PATH = WARDROBE_DIR / "items.json"
STYLE_PROFILE_PATH = WARDROBE_DIR / "style_profile.json"

_MEDIA_TYPES = {
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".png": "image/png",
    ".webp": "image/webp",
    ".gif": "image/gif",
}

_VISION_SYSTEM_PROMPT = """You are cataloging a photo of a single clothing item for a
wardrobe app. Respond with ONLY a JSON object with exactly these keys:
- category: one of "top", "bottom", "outerwear", "dress", "shoes", "accessory"
- subtype: short phrase, e.g. "flannel button-up" or "chino pants"
- primary_color: one word/short phrase
- secondary_colors: array of strings, can be empty
- warmth: integer 1-5 (1 = very light/summer only, 5 = heavy winter insulated)
- formality: one of "casual", "smart_casual", "formal", "athletic"
- rain_ok: boolean - materially fine to wear in light rain
- style_tags: array of 2-4 short descriptors (e.g. "minimalist", "streetwear", "preppy")
- description: one short sentence"""

_STYLE_SYSTEM_PROMPT = """Summarize this person's personal style from their wardrobe in
2-4 concrete sentences: color palette, fits/silhouettes, formality range, and any clear
aesthetic (e.g. minimalist, streetwear, prepwear, athletic/outdoorsy). Be specific, not
generic - this will be used to keep future outfit picks consistent with their taste."""

_GAPS_SYSTEM_PROMPT = """Look at this wardrobe (and style) and point out 3-6 specific
pieces that would meaningfully expand what outfits are possible. Focus on real gaps - a
missing category, no weather-appropriate option, no formal option - not just "buy more
clothes". Each suggestion should be one short, specific sentence, e.g. "A waterproof
shell jacket - you have no rain-ready outerwear."

Respond with ONLY a JSON array of strings."""


def ensure_dirs() -> None:
    IMAGES_DIR.mkdir(parents=True, exist_ok=True)


def _media_type(path: Path) -> str:
    return _MEDIA_TYPES.get(path.suffix.lower(), "image/jpeg")


def _item_to_dict(item: WardrobeItem) -> dict:
    d = asdict(item)
    d["added_at"] = item.added_at.isoformat()
    return d


def _item_from_dict(d: dict) -> WardrobeItem:
    d = dict(d)
    d["added_at"] = datetime.fromisoformat(d["added_at"])
    return WardrobeItem(**d)


def load_wardrobe() -> list[WardrobeItem]:
    if not ITEMS_PATH.exists():
        return []
    return [_item_from_dict(d) for d in json.loads(ITEMS_PATH.read_text())]


def save_wardrobe(items: list[WardrobeItem]) -> None:
    ensure_dirs()
    ITEMS_PATH.write_text(json.dumps([_item_to_dict(it) for it in items], indent=2))


def load_style_profile() -> StyleProfile | None:
    if not STYLE_PROFILE_PATH.exists():
        return None
    d = json.loads(STYLE_PROFILE_PATH.read_text())
    d["generated_at"] = datetime.fromisoformat(d["generated_at"])
    return StyleProfile(**d)


def save_style_profile(profile: StyleProfile) -> None:
    ensure_dirs()
    d = asdict(profile)
    d["generated_at"] = profile.generated_at.isoformat()
    STYLE_PROFILE_PATH.write_text(json.dumps(d, indent=2))


def analyze_clothing_image(
    image_path: Path, api_key: str, model: str, note: str | None = None
) -> dict:
    client = Anthropic(api_key=api_key)
    data = base64.standard_b64encode(image_path.read_bytes()).decode()
    text = "Catalog this clothing item." + (f"\nOwner's note: {note}" if note else "")
    response = client.messages.create(
        model=model,
        max_tokens=512,
        system=_VISION_SYSTEM_PROMPT,
        messages=[
            {
                "role": "user",
                "content": [
                    {
                        "type": "image",
                        "source": {
                            "type": "base64",
                            "media_type": _media_type(image_path),
                            "data": data,
                        },
                    },
                    {"type": "text", "text": text},
                ],
            }
        ],
    )
    response_text = "".join(b.text for b in response.content if b.type == "text")
    return parse_json_object(response_text)


def add_item(
    image_path: Path,
    api_key: str | None,
    model: str,
    manual: dict | None = None,
    note: str | None = None,
) -> WardrobeItem:
    ensure_dirs()
    item_id = uuid.uuid4().hex[:10]
    ext = image_path.suffix.lower() or ".jpg"
    dest_rel = f"images/{item_id}{ext}"
    dest = WARDROBE_DIR / dest_rel
    dest.write_bytes(image_path.read_bytes())

    if manual:
        fields = manual
    elif api_key:
        fields = analyze_clothing_image(dest, api_key, model, note)
    else:
        dest.unlink()
        raise RuntimeError(
            "Tagging a photo automatically needs ANTHROPIC_API_KEY. Set it in .env, "
            "or pass --manual with --category (and optionally --subtype/--color/--warmth/--formality)."
        )

    item = WardrobeItem(
        item_id=item_id,
        image_path=dest_rel,
        category=fields["category"],
        subtype=fields.get("subtype", ""),
        primary_color=fields.get("primary_color", ""),
        secondary_colors=list(fields.get("secondary_colors") or []),
        warmth=int(fields.get("warmth", 3)),
        formality=fields.get("formality", "casual"),
        rain_ok=bool(fields.get("rain_ok", False)),
        style_tags=list(fields.get("style_tags") or []),
        description=fields.get("description", ""),
        added_at=datetime.now().astimezone(),
    )

    items = load_wardrobe()
    items.append(item)
    save_wardrobe(items)
    return item


def remove_item(item_id: str) -> bool:
    items = load_wardrobe()
    remaining = [it for it in items if it.item_id != item_id]
    if len(remaining) == len(items):
        return False
    removed = next(it for it in items if it.item_id == item_id)
    image_path = WARDROBE_DIR / removed.image_path
    if image_path.exists():
        image_path.unlink()
    save_wardrobe(remaining)
    return True


def build_style_profile(
    items: list[WardrobeItem], style_notes: str, api_key: str | None, model: str
) -> StyleProfile:
    if not items:
        raise ValueError("Your wardrobe is empty - add some clothes first with `jarvis wardrobe add <photo>`.")
    if not api_key:
        raise RuntimeError("Building a style profile needs ANTHROPIC_API_KEY.")

    item_lines = "\n".join(
        f"- {it.category}/{it.subtype}: {it.primary_color}, {it.formality}, "
        f"style tags: {', '.join(it.style_tags)}"
        for it in items
    )
    prompt = f"Wardrobe:\n{item_lines}\n\nPerson's own notes on their style: {style_notes or '(none given)'}"

    client = Anthropic(api_key=api_key)
    response = client.messages.create(
        model=model,
        max_tokens=400,
        system=_STYLE_SYSTEM_PROMPT,
        messages=[{"role": "user", "content": prompt}],
    )
    summary = "".join(b.text for b in response.content if b.type == "text").strip()
    profile = StyleProfile(
        summary=summary, generated_at=datetime.now().astimezone(), based_on_item_count=len(items)
    )
    save_style_profile(profile)
    return profile


def _heuristic_gaps(items: list[WardrobeItem]) -> list[str]:
    gaps: list[str] = []
    categories = {it.category for it in items}

    for cat, label in [
        ("top", "tops"),
        ("bottom", "bottoms"),
        ("outerwear", "outerwear"),
        ("shoes", "shoes"),
    ]:
        if cat not in categories:
            gaps.append(f"You don't have any {label} logged yet.")

    max_outerwear_warmth = max((it.warmth for it in items if it.category == "outerwear"), default=0)
    if max_outerwear_warmth < 4:
        gaps.append("No heavy cold-weather coat logged - worth having one for the coldest days.")

    if not any(it.rain_ok for it in items if it.category in ("outerwear", "top")):
        gaps.append("Nothing rain-ready - a waterproof jacket would help on wet days.")

    if not any(it.formality in ("smart_casual", "formal") for it in items):
        gaps.append("No smart-casual/formal pieces logged - useful for interviews or career fairs.")

    if not any(it.formality == "athletic" for it in items):
        gaps.append("No dedicated athletic wear logged.")

    return gaps


def find_wardrobe_gaps(
    items: list[WardrobeItem],
    style_profile: StyleProfile | None,
    style_notes: str,
    api_key: str | None,
    model: str,
) -> list[str]:
    if not items:
        return ["Your wardrobe is empty - add some clothes with `jarvis wardrobe add <photo>` first."]
    if not api_key:
        return _heuristic_gaps(items)

    item_lines = "\n".join(
        f"- {it.category}/{it.subtype}: {it.primary_color}, warmth={it.warmth}/5, "
        f"{it.formality}, rain_ok={it.rain_ok}"
        for it in items
    )
    style_desc = style_profile.summary if style_profile else "(not yet analyzed)"
    prompt = f"Wardrobe:\n{item_lines}\n\nStyle: {style_desc}\nNotes: {style_notes or '(none)'}"

    try:
        client = Anthropic(api_key=api_key)
        response = client.messages.create(
            model=model,
            max_tokens=500,
            system=_GAPS_SYSTEM_PROMPT,
            messages=[{"role": "user", "content": prompt}],
        )
        text = "".join(b.text for b in response.content if b.type == "text")
        return [str(g) for g in parse_json_array(text)]
    except Exception:
        return _heuristic_gaps(items)
