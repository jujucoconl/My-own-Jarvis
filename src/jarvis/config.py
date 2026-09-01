"""Loads secrets from .env and user preferences from config/user.yaml."""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

import yaml
from dotenv import load_dotenv

REPO_ROOT = Path(__file__).resolve().parents[2]


@dataclass
class EmailAccountConfig:
    label: str
    provider: str  # "gmail" | "outlook"


@dataclass
class LocationConfig:
    city: str | None = None
    lat: float | None = None
    lon: float | None = None


@dataclass
class UserConfig:
    name: str
    location: LocationConfig
    wake_time: str
    sleep_time: str
    interests: list[str]
    email_accounts: list[EmailAccountConfig]
    max_emails_per_account: int = 20
    min_downtime_minutes: int = 30


@dataclass
class Secrets:
    anthropic_api_key: str | None
    anthropic_model: str
    google_credentials_path: Path
    google_token_path: Path
    ms_client_id: str | None
    ms_tenant_id: str
    ms_token_cache_path: Path


@dataclass
class AppConfig:
    user: UserConfig
    secrets: Secrets


def _load_user_config(path: Path) -> UserConfig:
    if not path.exists():
        example = path.with_name("user.example.yaml")
        raise FileNotFoundError(
            f"Missing {path}. Copy {example} to {path} and edit it first."
        )
    raw = yaml.safe_load(path.read_text()) or {}

    location_raw = raw.get("location", {}) or {}
    location = LocationConfig(
        city=location_raw.get("city"),
        lat=location_raw.get("lat"),
        lon=location_raw.get("lon"),
    )

    accounts = [
        EmailAccountConfig(label=a["label"], provider=a["provider"])
        for a in raw.get("email_accounts", []) or []
    ]

    return UserConfig(
        name=raw.get("name", "there"),
        location=location,
        wake_time=raw.get("wake_time", "07:00"),
        sleep_time=raw.get("sleep_time", "23:00"),
        interests=list(raw.get("interests", []) or []),
        email_accounts=accounts,
        max_emails_per_account=int(raw.get("max_emails_per_account", 20)),
        min_downtime_minutes=int(raw.get("min_downtime_minutes", 30)),
    )


def _load_secrets() -> Secrets:
    load_dotenv(REPO_ROOT / ".env")

    return Secrets(
        anthropic_api_key=os.getenv("ANTHROPIC_API_KEY") or None,
        anthropic_model=os.getenv("ANTHROPIC_MODEL", "claude-sonnet-5"),
        google_credentials_path=Path(
            os.getenv("GOOGLE_CREDENTIALS_PATH", "credentials.json")
        ),
        google_token_path=Path(os.getenv("GOOGLE_TOKEN_PATH", ".google_token.json")),
        ms_client_id=os.getenv("MS_CLIENT_ID") or None,
        ms_tenant_id=os.getenv("MS_TENANT_ID", "common"),
        ms_token_cache_path=Path(
            os.getenv("MS_TOKEN_CACHE_PATH", ".ms_token_cache.bin")
        ),
    )


def load_config(user_config_path: Path | None = None) -> AppConfig:
    path = user_config_path or (REPO_ROOT / "config" / "user.yaml")
    return AppConfig(user=_load_user_config(path), secrets=_load_secrets())
