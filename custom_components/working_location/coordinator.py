"""DataUpdateCoordinator and parsing logic for Working Location."""

from __future__ import annotations

import logging
from datetime import datetime, timedelta
from typing import Any

from aiohttp import ClientResponseError

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.util import dt as dt_util

from .api import GoogleCalendarApiClient
from .const import (
    DOMAIN,
    STATE_CUSTOM_LOCATION,
    STATE_HOME_OFFICE,
    STATE_NONE,
    STATE_OFFICE_LOCATION,
    STATE_UNKNOWN,
    VALID_STATES,
)

_LOGGER = logging.getLogger(__name__)


class WorkingLocationCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    """Coordinator that fetches and parses working location data."""

    def __init__(
        self,
        hass: HomeAssistant,
        api_client: GoogleCalendarApiClient,
        calendar_id: str,
        update_interval_minutes: int,
        consider_none_outside_hours: bool,
    ) -> None:
        """Initialise the coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=timedelta(minutes=update_interval_minutes),
        )
        self._api_client = api_client
        self._calendar_id = calendar_id
        self._consider_none_outside_hours = consider_none_outside_hours

    async def _async_update_data(self) -> dict[str, Any]:
        """Fetch events and return parsed state + attributes dict."""
        now = dt_util.now()

        # Build today's window in HA's local timezone (midnight → midnight)
        today_local = now.replace(hour=0, minute=0, second=0, microsecond=0)
        tomorrow_local = today_local + timedelta(days=1)

        time_min = today_local.isoformat()
        time_max = tomorrow_local.isoformat()

        try:
            response = await self._api_client.async_get_working_location_events(
                self._calendar_id, time_min, time_max
            )
        except ClientResponseError as err:
            if err.status == 401:
                raise ConfigEntryAuthFailed(
                    "Google Calendar token is no longer valid"
                ) from err
            raise UpdateFailed(
                f"Error communicating with Google Calendar API: {err}"
            ) from err
        except Exception as err:
            raise UpdateFailed(f"Unexpected error fetching working location: {err}") from err

        events: list[dict[str, Any]] = response.get("items", [])
        return _parse_events(events, now, self._calendar_id, self._consider_none_outside_hours)


# ---------------------------------------------------------------------------
# Pure parsing helpers (no HA imports needed, easy to unit-test)
# ---------------------------------------------------------------------------

def _parse_events(
    events: list[dict[str, Any]],
    now: datetime,
    calendar_id: str,
    consider_none_outside_hours: bool,
) -> dict[str, Any]:
    """Parse a list of working-location events into state + attributes.

    Selection logic:
    1. Prefer the event whose time range covers *now*.
    2. Fall back to the earliest event in the day (first in list; API orders
       by startTime).
    3. If no events: state = ``none``.
    """
    if not events:
        return {"state": STATE_NONE, "attributes": {"calendar_id": calendar_id}}

    # Try to find an event that covers "now"
    selected: dict[str, Any] | None = None
    for event in events:
        if _event_covers_now(event, now):
            selected = event
            break

    if selected is None:
        if consider_none_outside_hours:
            # No event covering now → treat as none
            return {"state": STATE_NONE, "attributes": {"calendar_id": calendar_id}}
        # Fall back to earliest event
        selected = events[0]

    return _extract_state_and_attrs(selected, calendar_id)


def _event_covers_now(event: dict[str, Any], now: datetime) -> bool:
    """Return True if the event's time range includes *now*."""
    start = event.get("start", {})
    end = event.get("end", {})

    if "dateTime" in start and "dateTime" in end:
        # Timed event — parse and compare
        start_dt = dt_util.parse_datetime(start["dateTime"])
        end_dt = dt_util.parse_datetime(end["dateTime"])
        if start_dt is not None and end_dt is not None:
            return start_dt <= now < end_dt
        return False

    if "date" in start:
        # All-day event — always covers any moment during the day
        return True

    return False


def _extract_state_and_attrs(
    event: dict[str, Any], calendar_id: str
) -> dict[str, Any]:
    """Extract sensor state and attributes from a single event."""
    wlp: dict[str, Any] = event.get("workingLocationProperties", {})
    loc_type: str | None = wlp.get("type")

    # Determine state
    if loc_type in VALID_STATES:
        state = loc_type
    else:
        state = STATE_UNKNOWN

    attrs: dict[str, Any] = {"calendar_id": calendar_id}

    # Mirror workingLocationProperties fields
    if loc_type:
        attrs["type"] = loc_type

    if "homeOffice" in wlp:
        attrs["homeOffice"] = wlp["homeOffice"]

    if "customLocation" in wlp:
        cl = wlp["customLocation"]
        if "label" in cl:
            attrs["customLocation_label"] = cl["label"]

    if "officeLocation" in wlp:
        ol: dict[str, Any] = wlp["officeLocation"]
        for field in ("buildingId", "floorId", "floorSectionId", "deskId", "label"):
            if field in ol:
                attrs[f"officeLocation_{field}"] = ol[field]

    # Attach raw workingLocationProperties when type is unrecognised
    if state == STATE_UNKNOWN and wlp:
        attrs["workingLocationProperties"] = wlp

    # Operational extras
    attrs["event_id"] = event.get("id")

    start = event.get("start", {})
    end = event.get("end", {})
    attrs["start"] = start.get("dateTime") or start.get("date")
    attrs["end"] = end.get("dateTime") or end.get("date")

    return {"state": state, "attributes": attrs}
