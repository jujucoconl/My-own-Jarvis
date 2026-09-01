# My-own-Jarvis

A personal morning-briefing assistant. Run `jarvis brief` and get, in one shot:

- **Weather + what to wear** - current conditions and a rule-based outfit suggestion.
- **Today's schedule** - pulled from Google Calendar.
- **Downtime suggestions** - free gaps between events, with an AI (or heuristic) suggestion for each based on the weather and your interests.
- **Email triage** - across multiple accounts (Gmail + Outlook), flags what's actually important, explains why, suggests a next step, and drafts a reply for anything that needs one.

Every integration fails independently and gracefully - if Outlook isn't configured, or Claude's API is unreachable, the rest of the briefing still runs and the gap is called out at the bottom under "Notes".

## How it's built

```
src/jarvis/
  weather.py         Open-Meteo (no API key needed) + geocoding
  outfit.py           rule-based "what to wear" from the weather
  calendar_google.py   Google Calendar (OAuth) -> today's events
  email_gmail.py        Gmail (OAuth) -> recent inbox messages, optional draft creation
  email_outlook.py       Outlook / Microsoft 365 (device-code login) -> recent inbox, optional draft creation
  importance.py            Claude-based email triage (importance/reason/next step/draft), heuristic fallback
  downtime.py                free-slot finder + Claude-based (or heuristic) activity suggestions
  briefing.py                  orchestrates everything into one Briefing object
  render.py                      Briefing -> Markdown
  cli.py                          `jarvis brief` entrypoint
```

Claude (via the Anthropic API) is used for the two genuinely "judgment" tasks - deciding
what's important and drafting a reply, and picking a downtime activity - and everything
else has a keyword/rule fallback so the tool still works without an API key.

## Setup

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"

cp config/user.example.yaml config/user.yaml   # edit: location, wake/sleep time, interests, email accounts
cp .env.example .env                           # edit: API keys (see below)
```

### 1. Claude (email triage, drafting, downtime suggestions)

Get an API key from the [Anthropic Console](https://console.anthropic.com/) and set
`ANTHROPIC_API_KEY` in `.env`. Optional - without it, Jarvis falls back to keyword-based
triage and canned downtime suggestions.

### 2. Google (Gmail + Calendar)

1. Create a project in the [Google Cloud Console](https://console.cloud.google.com/apis/credentials),
   enable the **Gmail API** and **Google Calendar API**.
2. Create an **OAuth client ID** of type "Desktop app" and download the JSON.
3. Save it as `credentials.json` in the repo root (or point `GOOGLE_CREDENTIALS_PATH` at it).
4. First run opens a browser for consent; after that a cached token (`.google_token.json`) is reused.

### 3. Microsoft 365 / Outlook

1. Register an app in [Azure AD App registrations](https://portal.azure.com) as a
   **public client** (mobile/desktop) - no client secret needed.
2. Add the delegated Graph permissions `Mail.Read` and `Mail.ReadWrite`.
3. Set `MS_CLIENT_ID` (and `MS_TENANT_ID` if not using a personal/multi-tenant default) in `.env`.
4. First run prints a device-login code/URL to sign in; after that a cached token
   (`.ms_token_cache.bin`) is reused.

None of the credential/token files above are committed - they're all in `.gitignore`.

## Usage

```bash
jarvis brief                          # print today's briefing to the terminal
jarvis brief --output briefing.md     # save it instead
jarvis brief --create-drafts          # also save the AI-drafted replies as real Gmail/Outlook drafts (opt-in, never auto-sends)
```

### Running it every morning

`jarvis brief` is a script, not a daemon - point cron (or Task Scheduler on Windows) at it:

```cron
# 6:45am on weekdays
45 6 * * 1-5 cd /path/to/My-own-Jarvis && .venv/bin/jarvis brief --output ~/briefings/$(date +\%F).md
```

## Tests

```bash
pytest
```

Tests cover the pure logic (outfit rules, free-slot math, heuristic email triage,
Markdown rendering) - no live network/API calls, no credentials required.
