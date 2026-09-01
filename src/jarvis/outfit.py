"""Rule-based "what to wear" suggestion from the day's weather."""

from __future__ import annotations

from jarvis.models import OutfitSuggestion, WeatherInfo


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
