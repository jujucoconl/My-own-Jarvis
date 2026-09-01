"""What to wear: a rule-based weather-only fallback, and a wardrobe-aware picker that
chooses from clothes you actually own and matches your style."""

from __future__ import annotations

from anthropic import Anthropic

from jarvis.ai_json import parse_json_object
from jarvis.models import OutfitSuggestion, StyleProfile, WardrobeItem, WeatherInfo

_WARDROBE_SYSTEM_PROMPT = """You are a personal stylist choosing today's outfit from
clothes the person actually owns. Respect their style profile and notes - don't just
optimize for weather, make it look like *them*. Pick items that work together and suit
today's weather and schedule.

If nothing in the wardrobe covers a real need today (e.g. no rain jacket on a rainy day,
no warm-enough coat), say so briefly in missing_piece_note - otherwise leave it null.
Don't invent items that aren't in the wardrobe list.

Respond with ONLY a JSON object with exactly these keys: chosen_item_ids (array of the
wardrobe item ids you picked), rationale (one short sentence on why this outfit), and
missing_piece_note (string or null)."""


def suggest_outfit(weather: WeatherInfo) -> OutfitSuggestion:
    details: list[str] = []

    low, high, feels = weather.temp_low_c, weather.temp_high_c, weather.feels_like_c

    if feels <= -5:
        base = "Heavy winter coat"
        details.append("Thermal base layer, hat, and gloves - it's brutal out there.")
    elif feels <= 5:
        base = "Winter coat"
        details.append("Hat and gloves recommended.")
    elif feels <= 12:
        base = "Warm jacket"
        details.append("A sweater or hoodie underneath works well.")
    elif feels <= 18:
        base = "Light jacket or hoodie"
    elif feels <= 24:
        base = "T-shirt, light layers optional"
    else:
        base = "T-shirt / shorts weather"
        details.append("Stay hydrated if you're outside for a while.")

    if high - low >= 10:
        details.append(
            f"Big swing today ({low:.0f}-{high:.0f} C) - layer so you can adjust."
        )

    if weather.precipitation_probability >= 60:
        details.append("High chance of rain - bring an umbrella or a rain shell.")
    elif weather.precipitation_probability >= 30:
        details.append("Rain's possible - worth grabbing an umbrella just in case.")

    if weather.wind_kph >= 30:
        details.append("Windy - a windbreaker layer will help.")

    summary = base
    if weather.precipitation_probability >= 30:
        summary += " + umbrella"

    return OutfitSuggestion(summary=summary, details=details)


def _describe_weather(weather: WeatherInfo) -> str:
    return (
        f"{weather.condition}, {weather.temp_now_c:.0f}C now (feels {weather.feels_like_c:.0f}C), "
        f"high {weather.temp_high_c:.0f}C / low {weather.temp_low_c:.0f}C, "
        f"{weather.precipitation_probability}% chance of rain, wind {weather.wind_kph:.0f} kph"
    )


def _describe_item(item: WardrobeItem) -> str:
    colors = item.primary_color
    if item.secondary_colors:
        colors += f" ({', '.join(item.secondary_colors)})"
    return (
        f"[{item.item_id}] {item.category}/{item.subtype} - {colors}, "
        f"warmth={item.warmth}/5, {item.formality}, rain_ok={item.rain_ok}, "
        f"style={', '.join(item.style_tags)}"
    )


def choose_outfit(
    weather: WeatherInfo | None,
    wardrobe: list[WardrobeItem],
    style_profile: StyleProfile | None,
    style_notes: str,
    event_titles: list[str],
    api_key: str | None,
    model: str,
) -> OutfitSuggestion:
    """Picks an outfit from the wardrobe when possible, otherwise falls back to the
    generic weather-only rule-based suggestion (and says why)."""
    if not weather:
        return OutfitSuggestion(summary="Weather unavailable", details=[])

    if not wardrobe:
        fallback = suggest_outfit(weather)
        fallback.details.append(
            "Add clothes with `jarvis wardrobe add <photo>` to get suggestions from what you actually own."
        )
        return fallback

    if not api_key:
        fallback = suggest_outfit(weather)
        fallback.details.append("Set ANTHROPIC_API_KEY to get outfit picks from your actual wardrobe.")
        return fallback

    item_lines = "\n".join(_describe_item(it) for it in wardrobe)
    style_desc = style_profile.summary if style_profile else "(not yet analyzed - run `jarvis wardrobe style`)"
    events_desc = "; ".join(event_titles) if event_titles else "nothing scheduled"

    prompt = (
        f"Weather today: {_describe_weather(weather)}\n"
        f"Today's schedule: {events_desc}\n"
        f"Style profile (derived from their wardrobe): {style_desc}\n"
        f"Additional style notes from the person: {style_notes or '(none)'}\n\n"
        f"Wardrobe:\n{item_lines}\n\n"
        "Pick a complete outfit (top, bottom or dress, outerwear if needed, shoes if "
        "available) from the wardrobe above."
    )

    try:
        client = Anthropic(api_key=api_key)
        response = client.messages.create(
            model=model,
            max_tokens=512,
            system=_WARDROBE_SYSTEM_PROMPT,
            messages=[{"role": "user", "content": prompt}],
        )
        text = "".join(b.text for b in response.content if b.type == "text")
        data = parse_json_object(text)

        chosen_ids = set(data.get("chosen_item_ids") or [])
        chosen = [it for it in wardrobe if it.item_id in chosen_ids]
        if not chosen:
            raise ValueError("Model didn't choose any known wardrobe items.")

        summary = ", ".join(it.subtype or it.category for it in chosen)
        details = [data["rationale"]] if data.get("rationale") else []
        return OutfitSuggestion(
            summary=summary,
            details=details,
            items=chosen,
            missing_piece_note=data.get("missing_piece_note") or None,
        )
    except Exception:
        fallback = suggest_outfit(weather)
        fallback.details.append("(Couldn't get a wardrobe-based pick this time - showing a generic suggestion.)")
        return fallback
