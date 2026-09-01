# My-own-Jarvis

A personal morning-briefing assistant. Run `jarvis brief` and get, in one shot:

- **Weather + what to wear** - current conditions, and an outfit picked from clothes you
  actually own (if you've uploaded any - see [Wardrobe & style](#wardrobe--style) below),
  in your own style. Falls back to a generic rule-based suggestion otherwise.
- **Today's schedule** - pulled from Google Calendar.
- **Downtime suggestions** - free gaps between events, with an AI (or heuristic) suggestion
  for each based on the weather, who you are, and what's happening right before/after the gap.
- **Email triage** - across multiple accounts (Gmail + Outlook), flags what's actually important, explains why, suggests a next step, and drafts a reply for anything that needs one.
- **Deadlines coming up** - anything you're tracking with `jarvis task` due in the next few days
  (see [Deadlines & the week ahead](#deadlines--the-week-ahead) below).

Every integration fails independently and gracefully - if Outlook isn't configured, or Claude's API is unreachable, the rest of the briefing still runs and the gap is called out at the bottom under "Notes".

It can also run itself: `jarvis schedule install` sets up a real weekday-morning cron
job (or Task Scheduler entry on Windows) so you stop having to remember to run it - see
[Running it every morning](#running-it-every-morning).

## How it's built

```
src/jarvis/
  weather.py          Open-Meteo (no API key needed) + geocoding
  outfit.py            rule-based weather-only fallback + wardrobe-aware outfit picker
  wardrobe.py            photo -> tagged item (Claude vision), style profile, gap-finder
  calendar_google.py       Google Calendar (OAuth, read/write) -> events, +create/delete
  email_gmail.py             Gmail (OAuth) -> recent inbox messages, optional draft creation
  email_outlook.py             Outlook / Microsoft 365 (device-code login) -> recent inbox, optional draft creation
  importance.py                  Claude-based email triage (importance/reason/next step/draft), heuristic fallback
  downtime.py                      free-slot finder + Claude-based (or heuristic) activity suggestions
  tasks.py                           deadlines you track, mirrored onto Google Calendar
  week.py                              7-day look-ahead: calendar events + tracked deadlines
  schedule.py                           installs `jarvis brief` as a cron / Task Scheduler job
  ai_json.py                              shared "pull JSON out of a Claude response" helper
  briefing.py                               orchestrates everything into one Briefing object
  render.py                                   Briefing / WeeklyLookahead -> Markdown
  cli.py                                        `jarvis brief` / `wardrobe` / `task` / `week` / `schedule`
```

Claude (via the Anthropic API) is used for the genuinely "judgment" tasks - deciding what's
important and drafting a reply, tagging a clothing photo, picking an outfit and downtime
activity that fit you - and everything else (weather, the base outfit rule, free-slot math,
heuristic email triage) has a fallback so the tool still works without an API key.

## Setup

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"

cp config/user.example.yaml config/user.yaml   # edit: location, wake/sleep time, about_me, style notes, email accounts
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

Jarvis asks for full (not read-only) Calendar access, since `jarvis task add` creates a
matching event for each deadline you track. If you set this up before that feature
existed, delete `.google_token.json` once - Jarvis notices the cached token is missing
the new scope and reruns the consent screen automatically on the next command.

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

## Wardrobe & style

Outfit suggestions get real once you tell Jarvis what you actually own:

```bash
jarvis wardrobe add photo.jpg               # Claude looks at the photo and tags it
                                              # (category, color, warmth, formality, style)
jarvis wardrobe add photo.jpg --note "runs small, wear loose"

jarvis wardrobe list                         # see everything you've logged
jarvis wardrobe remove <item_id>

jarvis wardrobe style                        # (re)generate a style summary from your wardrobe
                                              # + the notes in config/user.yaml's `style.notes`
jarvis wardrobe gaps                         # "3-6 specific pieces worth adding, and why"
```

Photos and derived data live under `wardrobe/` (gitignored - it's your stuff, not the repo's).
No `ANTHROPIC_API_KEY`? You can still log items by hand: `jarvis wardrobe add photo.jpg
--manual --category top --subtype "flannel shirt" --color red --warmth 3 --formality casual`.

Once you've got a few items logged, `jarvis brief` picks a real outfit from them - it
weighs today's weather and schedule against your wardrobe and style (both the profile
generated from your clothes and your own `style.notes`), and flags it in the briefing
("Heads up: ...") on days your wardrobe genuinely doesn't have the right thing (no rain
jacket on a rainy day, etc.) rather than nagging you every day. Run `jarvis wardrobe gaps`
whenever you want the fuller "what should I actually buy" picture.

## Deadlines & the week ahead

Track a deadline once and it shows up everywhere: today's brief (if it's coming up soon),
`jarvis week`, and your actual Google Calendar.

```bash
jarvis task add "Lab report" --due 2026-09-05 --time 23:59 --course "ME 270" --priority high
jarvis task add "Career fair" --due 2026-09-10 --no-calendar   # skip the calendar sync

jarvis task list                # what's due in the next 7 days
jarvis task list --all          # everything, including completed
jarvis task done <task_id>
jarvis task remove <task_id>    # also deletes the linked calendar event

jarvis week                     # day-by-day look-ahead: events + deadlines, next 7 days
jarvis week --output week.md
```

`jarvis task add` creates a matching all-day event on your Google Calendar titled
`Due: <title>` by default (`--no-calendar` to skip that). `jarvis week` pulls that same
week's calendar events plus everything you're tracking, and - with `ANTHROPIC_API_KEY`
set - adds a short "here's what this week actually looks like" heads-up (busiest days,
what needs starting soonest) on top of the plain day-by-day listing. `jarvis brief`
surfaces anything due in the next 3 days so you don't have to open `jarvis week` daily.
Deadlines live in `tasks/tasks.json` (gitignored, personal data, same pattern as `wardrobe/`).

## Running it every morning

`jarvis brief` is a script, not a daemon - `jarvis schedule` turns it into one:

```bash
jarvis schedule install                       # cron/Task Scheduler, weekdays at 06:45 by default
jarvis schedule install --time 07:15           # different time
jarvis schedule status                         # see what's currently installed
jarvis schedule uninstall
```

This installs a real OS-level job (cron on Linux/macOS, Task Scheduler on Windows) that
runs `jarvis brief --output briefings/<date>.md` in this repo's virtualenv - `jarvis
schedule install` re-run later replaces the old entry rather than duplicating it. If you'd
rather manage it by hand (or `crontab` isn't available), the equivalent line is:

```cron
# 6:45am on weekdays
45 6 * * 1-5 cd /path/to/My-own-Jarvis && .venv/bin/jarvis brief --output briefings/$(date +\%F).md
```

## Tests

```bash
pytest
```

Tests cover the pure logic (outfit rules, free-slot math, heuristic email triage,
wardrobe storage + gap heuristics, task tracking, cron-line building, Markdown
rendering) - no live network/API calls, no credentials required.
