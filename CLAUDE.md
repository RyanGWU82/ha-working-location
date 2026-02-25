# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This is a Home Assistant custom integration called **"Google Calendar Working Location"** (`working_location`). It exposes a single sensor entity (`sensor.working_location`) that reads the user's Google Calendar "working location" events via the Google Calendar API v3.

The full spec is in `SPEC.md`. The integration lives under `custom_components/working_location/`.

## File Layout

```
hacs.json                              # HACS marketplace metadata (repo root)
README.md                              # HACS-ready README (repo root; HACS reads root)
custom_components/working_location/
  __init__.py        # Setup entry, coordinator init
  config_flow.py     # OAuth2 config flow + post-setup options flow
  const.py           # Domain, defaults, scope, endpoints
  api.py             # Thin Calendar API client (aiohttp)
  coordinator.py     # DataUpdateCoordinator + parsing logic
  sensor.py          # SensorEntity, state + attributes mapping
  manifest.json      # dependencies: ["application_credentials"]
  strings.json       # UI text keys
  translations/en.json
```

## Key Architecture Decisions

**Minimum HA version:** 2024.1+. Use `async_forward_entry_setups` (plural), not the older singular form.

**OAuth / credentials:** Uses HA's `application_credentials` component and `AbstractOAuth2FlowHandler`. Tokens are stored in the config entry and auto-refreshed by HA helpers — no manual token handling. Scope: `https://www.googleapis.com/auth/calendar.events.readonly` (events read-only, not full calendar scope).

**Config flow vs options flow:** The initial config flow is OAuth only. Optional settings (calendar ID, update interval, consider_none_outside_hours) live in the **options flow** (post-setup "Configure" button), stored in `entry.options`. The integration registers `add_update_listener` → `async_reload` so changing options triggers a full reload to pick up new coordinator settings.

**Data fetching:** `DataUpdateCoordinator` in `coordinator.py` calls `Events.list` each update cycle (default 5 min). Query parameters:
- `timeMin` / `timeMax` = today midnight–midnight in HA's local timezone (RFC3339)
- `singleEvents=true`, `orderBy=startTime`, `eventTypes=workingLocation`
- Use `async_config_entry_first_refresh()` for the initial fetch on setup.

**Event selection logic** (multiple events in one day): prefer the event whose time range covers "now"; fall back to the earliest event. All-day events (`start.date` format) always count as covering "now" — no time comparison required.

**Sensor state values:** `homeOffice` | `officeLocation` | `customLocation` | `none` | `unknown`

**Attributes:** mirror `workingLocationProperties` fields (see SPEC.md §Entity for full list) plus operational extras: `event_id`, `start`, `end`, `calendar_id`.

**Unique ID:** scoped to `{entry.entry_id}_working_location` (not calendar_id) so multiple accounts can coexist without collision.

**Entity naming:** use `_attr_has_entity_name = True` with `_attr_name = "Working Location"` for the modern HA entity naming pattern.

**Error handling:**
- HTTP 401 (startup or runtime) → `ConfigEntryAuthFailed`; triggers HA's re-authentication UI
- Other HTTP/network errors on startup → `ConfigEntryNotReady`; HA retries setup
- Other runtime errors in coordinator → `UpdateFailed`; coordinator keeps last good data, `available` goes False
- Token validated at startup with `session.async_ensure_token_valid()` before creating the coordinator

## HA Integration Patterns

- Use `homeassistant.helpers.update_coordinator.DataUpdateCoordinator`
- Use `homeassistant.components.application_credentials` for OAuth client credential storage
- Config flow should extend `homeassistant.helpers.config_entry_oauth2_flow.AbstractOAuth2FlowHandler`
- API client in `api.py` uses the session from `OAuth2Session` (wraps aiohttp) via `session.async_request`
- OAuth scope: `https://www.googleapis.com/auth/calendar.events.readonly`
- Calendar API endpoint: `https://www.googleapis.com/calendar/v3/calendars/{calendarId}/events`
- Options flow: extend `homeassistant.config_entries.OptionsFlow`; return from `AbstractOAuth2FlowHandler.async_get_options_flow`

## Testing

No test framework is set up yet. When adding tests, follow HA's convention of using `pytest` with `pytest-homeassistant-custom-component` for custom integration testing.

To run tests once configured:
```bash
pytest tests/
```
