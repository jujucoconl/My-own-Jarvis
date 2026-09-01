from jarvis.models import WeatherInfo
from jarvis.outfit import suggest_outfit


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
