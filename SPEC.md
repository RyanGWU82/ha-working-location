# Home Assistant custom integration spec: “Google Calendar Working Location”
#computers

# Goal
Expose a sensor entity (`sensor.working_location`) and a calendar entity (`calendar.working_location`) that reflect Google Calendar “working location” for the current day by reading the user’s primary calendar via the Google Calendar API. Working location is represented by events with `eventType: “workingLocation”` and a `workingLocationProperties` object.
# Non-goals
No second calendar. No manual “WFH” events. No write-back to Google Calendar.
# User experience
The integration is configured via the UI. User provides Google OAuth client credentials via Home Assistant “Application Credentials” and completes OAuth authorization in Home Assistant. Tokens are stored in the config entry and auto-refreshed using HA’s OAuth2 helpers.
# Entity
**Entity name:** `sensor.working_location`

**State (string, normalized):** `homeOffice`, `officeLocation`, `customLocation`, `none` (no working location set for today), `unknown` (API error / unexpected shape)

**Attributes:** mirror Google’s workingLocationProperties; omit fields not present
* `type` (same as state when state is one of the three location types)
* `homeOffice` (raw object/value if present; Google documents it as “any value”)
* `customLocation_label` (from workingLocationProperties.customLocation.label)
* `officeLocation_buildingId`
* `officeLocation_floorId`
* `officeLocation_floorSectionId`
* `officeLocation_deskId`
* `officeLocation_label`

**Helpful extra attributes:** not from workingLocationProperties but useful operationally
* event_id (the event’s id)
* start / end (RFC3339 from event.start / event.end; all-day vs timed supported)
* calendar_id (always primary unless you later add an option)
* is_workday (bool) — `true` when state is one of the three location types (`homeOffice`, `officeLocation`, `customLocation`); `false` when state is `none` or `unknown`
# Calendar entity
**Entity name:** `calendar.working_location`

Exposes working location events to the HA Calendar UI.

**`event` property:** returns the currently-active working location event (derived from coordinator data — no extra API call).

**`async_get_events(start_date, end_date)`:** called by the HA Calendar card when rendering a date range. Makes a direct API call with the requested range (same parameters as the coordinator but with caller-supplied `timeMin`/`timeMax`).

**Event summary mapping:**
| `workingLocationProperties.type` | Summary shown in calendar |
|---|---|
| `homeOffice` | Home Office |
| `officeLocation` | Office |
| `customLocation` | Custom Location |
| `none` | Not Working |
| *(other)* | raw type string |

All-day events (`start.date`) and timed events (`start.dateTime`) are both supported and passed through to HA as `date` or `datetime` objects respectively.

# Configuration / options
**Initial config flow:** OAuth only — Application Credentials selection and OAuth dance. No optional fields here.

**Options flow** (post-setup, via the integration’s “Configure” button):
* “Calendar id” (default `primary`)
* “Update interval” in minutes (default 5, minimum 1)
* “Consider ‘none’ outside working hours” (default false; when true, state is `none` if no event covers the current time)
# OAuth / scopes
Use HA OAuth2 implementation. Scope: `https://www.googleapis.com/auth/calendar.events.readonly` (narrower than the full calendar scope — events read-only is sufficient). Use the standard Calendar API v3 endpoint for listing events.
# Data fetching
Use a DataUpdateCoordinator. Every update cycle, query `Events.list` for the local “today” window (midnight to midnight in HA’s timezone), with:
* `timeMin` = today 00:00:00 local offset (RFC3339)
* `timeMax` = tomorrow 00:00:00 local offset (RFC3339)
* `singleEvents=true`
* `orderBy=startTime`
* `eventTypes=workingLocation` (to reduce payload and avoid parsing unrelated events)
# Parsing rules
* If API returns 0 items: state = `none`.
* If 1+ workingLocation events exist for the day: pick the one that covers “now” if any; else pick the earliest event in the day. (This handles partial-day office/home splits.)
* Extract `workingLocationProperties` and map exactly as documented: type plus the nested objects/fields.
* If type is missing/unknown: state=`unknown`, still attach raw `workingLocationProperties` in attributes if present.
# Edge cases / correctness
* All-day vs timed: support both `start.date` and `start.dateTime` formats. All-day events (`start.date`) always count as “covering now” for the whole day — no time comparison needed.
* Multiple segments in one day: choose “current” segment first; else earliest.
* API transient failures: keep last good state, set available=false on entity, log warning with rate limiting.
* Token refresh / auth errors (HTTP 401): raise `ConfigEntryAuthFailed` on startup and in the coordinator — this triggers HA's built-in re-authentication UI prompt.
* Other startup errors (network, non-401 HTTP): raise `ConfigEntryNotReady` so HA retries setup.
* Other runtime errors in coordinator: raise `UpdateFailed`; coordinator keeps last good data and sets `last_update_success=False`.
# File layout
Repo root:
* `README.md` — HACS reads the root README; this is the canonical user-facing doc
* `hacs.json` — HACS marketplace metadata

`custom_components/working_location/`:
* `manifest.json` (dependencies: `application_credentials`)
* `__init__.py` (setup entry, coordinator init)
* `config_flow.py` (Application Credentials + OAuth2 flow + options flow)
* `const.py` (domain, defaults, scope, endpoints)
* `api.py` (thin Calendar API client wrapper using aiohttp)
* `coordinator.py` (DataUpdateCoordinator + parsing)
* `sensor.py` (SensorEntity, state + attributes mapping)
* `calendar.py` (CalendarEntity, event + async_get_events)
* `strings.json` / `translations/en.json` (UI text)
# Testing strategy
Tests live in `tests/` and run with `pytest` (no real HA installation required).

**Approach:** The HA package is stubbed out via `sys.modules` patching in `tests/conftest.py`. Stub classes replace `DataUpdateCoordinator`, `CoordinatorEntity`, `SensorEntity`, and `dt_util` so the integration code can be imported and exercised using only `aiohttp`, `pytest`, and `pytest-asyncio`.

**Coverage:**
* `_event_covers_now` — all-day, timed, boundary conditions, Z-suffix UTC, unparseable datetimes
* `_extract_state_and_attrs` — all location types, field presence/absence, unknown/missing type, operational extras
* `_parse_events` — empty list, single event, multi-event selection, `consider_none_outside_hours` both ways
* `WorkingLocationCoordinator._async_update_data` — success, 401 auth failure, non-401 HTTP error, generic exception, time window, calendar_id forwarding
* `GoogleCalendarApiClient` — URL construction, query params, `raise_for_status`, HTTP error propagation
* `WorkingLocationSensor` — native_value, extra_state_attributes, available logic, unique_id, entity name/icon
* `WorkingLocationCalendar` — event property (timed/all-day/no-data), async_get_events (success, empty, API error, unexpected error)
* `_build_calendar_event` — timed events, all-day events, unknown type, None inputs, invalid date/datetime strings

**Running tests:**
```bash
python -m venv .venv && .venv/bin/pip install -r requirements_test.txt
.venv/bin/python -m pytest
```

# Acceptance criteria
* After OAuth setup, `sensor.working_location` appears and updates.
* When the user sets working location to home/office/custom for today in Google Calendar UI, HA reflects the corresponding type and attributes as documented.
* No manual token handling by the user after setup (auto-refresh works via HA helpers).
# References
* [Google Calendar - Events API reference](https://developers.google.com/workspace/calendar/api/v3/reference/events)
* [Home Assistant - Application Credentials integration](https://www.home-assistant.io/integrations/application_credentials/?utm_source=chatgpt.com)