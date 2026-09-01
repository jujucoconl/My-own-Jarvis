"""Weather via Open-Meteo (no API key required)."""

from __future__ import annotations

import requests

from jarvis.config import LocationConfig
from jarvis.models import WeatherInfo

GEOCODE_URL = "https://geocoding-api.open-meteo.com/v1/search"
FORECAST_URL = "https://api.open-meteo.com/v1/forecast"

# https://open-meteo.com/en/docs#weathervariables (WMO weather codes)
_CONDITION_BY_CODE = {
    0: "clear sky",
    1: "mostly clear",
    2: "partly cloudy",
    3: "overcast",
    45: "fog",
    48: "depositing rime fog",
    51: "light drizzle",
    53: "drizzle",
    55: "dense drizzle",
    56: "freezing drizzle",
    57: "freezing drizzle",
    61: "light rain",
    63: "rain",
    65: "heavy rain",
    66: "freezing rain",
    67: "freezing rain",
    71: "light snow",
    73: "snow",
    75: "heavy snow",
    77: "snow grains",
    80: "light rain showers",
    81: "rain showers",
    82: "violent rain showers",
    85: "snow showers",
    86: "heavy snow showers",
    95: "thunderstorm",
    96: "thunderstorm with hail",
    99: "thunderstorm with heavy hail",
}


def describe_condition(code: int) -> str:
    return _CONDITION_BY_CODE.get(code, "unknown conditions")


def geocode_city(city: str) -> tuple[float, float]:
    resp = requests.get(GEOCODE_URL, params={"name": city, "count": 1}, timeout=10)
    resp.raise_for_status()
    results = resp.json().get("results")
    if not results:
        raise ValueError(f"Could not find a location for '{city}'.")
    top = results[0]
    return top["latitude"], top["longitude"]


def resolve_coordinates(location: LocationConfig) -> tuple[float, float]:
    if location.lat is not None and location.lon is not None:
        return location.lat, location.lon
    if not location.city:
        raise ValueError("config/user.yaml needs either location.city or lat/lon.")
    return geocode_city(location.city)


def get_weather(location: LocationConfig) -> WeatherInfo:
    lat, lon = resolve_coordinates(location)
    resp = requests.get(
        FORECAST_URL,
        params={
            "latitude": lat,
            "longitude": lon,
            "current": "temperature_2m,apparent_temperature,precipitation,weather_code,wind_speed_10m,is_day",
            "daily": "temperature_2m_max,temperature_2m_min,precipitation_probability_max",
            "timezone": "auto",
        },
        timeout=10,
    )
    resp.raise_for_status()
    data = resp.json()
    current = data["current"]
    daily = data["daily"]

    return WeatherInfo(
        condition=describe_condition(current["weather_code"]),
        temp_now_c=current["temperature_2m"],
        temp_high_c=daily["temperature_2m_max"][0],
        temp_low_c=daily["temperature_2m_min"][0],
        feels_like_c=current["apparent_temperature"],
        precipitation_probability=daily["precipitation_probability_max"][0] or 0,
        wind_kph=current["wind_speed_10m"],
        is_daytime=bool(current.get("is_day", 1)),
    )
