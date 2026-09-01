from datetime import datetime

from jarvis.models import WardrobeItem, WeatherInfo
from jarvis.outfit import choose_outfit, suggest_outfit


def _weather(**overrides) -> WeatherInfo:
    base = dict(
        condition="clear sky",
        temp_now_c=20,
        temp_high_c=22,
        temp_low_c=18,
        feels_like_c=20,
        precipitation_probability=0,
        wind_kph=5,
    )
    base.update(overrides)
    return WeatherInfo(**base)


def test_cold_weather_suggests_winter_coat():
    result = suggest_outfit(_weather(feels_like_c=-10, temp_low_c=-12, temp_high_c=-5))
    assert "coat" in result.summary.lower()


def test_hot_weather_suggests_light_clothing():
    result = suggest_outfit(_weather(feels_like_c=28, temp_low_c=24, temp_high_c=30))
    assert "t-shirt" in result.summary.lower() or "shorts" in result.summary.lower()


def test_rain_adds_umbrella_to_summary():
    result = suggest_outfit(_weather(precipitation_probability=70))
    assert "umbrella" in result.summary.lower()


def test_big_temperature_swing_is_flagged():
    result = suggest_outfit(_weather(temp_low_c=5, temp_high_c=22))
    assert any("swing" in d.lower() for d in result.details)


def test_windy_adds_windbreaker_note():
    result = suggest_outfit(_weather(wind_kph=40))
    assert any("wind" in d.lower() for d in result.details)


def _wardrobe_item() -> WardrobeItem:
    return WardrobeItem(
        item_id="1",
        image_path="images/1.jpg",
        category="top",
        subtype="t-shirt",
        primary_color="black",
        secondary_colors=[],
        warmth=2,
        formality="casual",
        rain_ok=False,
        style_tags=["minimalist"],
        description="",
        added_at=datetime(2026, 9, 1),
    )


def test_choose_outfit_returns_placeholder_when_weather_missing():
    result = choose_outfit(None, [], None, "", [], api_key=None, model="unused")
    assert result.items == []


def test_choose_outfit_falls_back_and_nudges_when_wardrobe_empty():
    result = choose_outfit(_weather(), [], None, "", [], api_key="fake-key", model="unused")
    assert result.items == []
    assert any("wardrobe add" in d.lower() for d in result.details)


def test_choose_outfit_falls_back_without_api_key():
    result = choose_outfit(_weather(), [_wardrobe_item()], None, "", [], api_key=None, model="unused")
    assert result.items == []
    assert any("anthropic_api_key" in d.lower() for d in result.details)
