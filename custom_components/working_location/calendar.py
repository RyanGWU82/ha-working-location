"""Calendar platform for Google Calendar Working Location."""

from __future__ import annotations

import logging
from datetime import date, datetime
from typing import Any

from aiohttp import ClientResponseError

from homeassistant.components.calendar import CalendarEntity, CalendarEvent
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.util import dt as dt_util

from .const import CONF_CALENDAR_ID, DEFAULT_CALENDAR_ID, DOMAIN
from .coordinator import WorkingLocationCoordinator

_LOGGER = logging.getLogger(__name__)

_LOCATION_SUMMARIES: dict[str, str] = {
    "homeOffice": "Home Office",
    "officeLocation": "Office",
    "customLocation": "Custom Location",
    "none": "Not Working",
}


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the working location calendar from a config entry."""
    coordinator: WorkingLocationCoordinator = hass.data[DOMAIN][entry.entry_id]
    calendar_id = entry.options.get(CONF_CALENDAR_ID, DEFAULT_CALENDAR_ID)
    async_add_entities([WorkingLocationCalendar(coordinator, entry, calendar_id)])


class WorkingLocationCalendar(CoordinatorEntity[WorkingLocationCoordinator], CalendarEntity):
    """Calendar entity exposing working location events."""

    _attr_has_entity_name = True
    _attr_name = "Working Location"

    def __init__(
        self,
        coordinator: WorkingLocationCoordinator,
        entry: ConfigEntry,
        calendar_id: str,
    ) -> None:
        """Initialise the calendar entity."""
        super().__init__(coordinator)
        self._calendar_id = calendar_id
        self._attr_unique_id = f"{entry.entry_id}_working_location_cal"

    @property
    def event(self) -> CalendarEvent | None:
        """Return the current working location event."""
        if self.coordinator.data is None:
            return None
        attrs = self.coordinator.data.get("attributes", {})
        start_str = attrs.get("start")
        end_str = attrs.get("end")
        loc_type = self.coordinator.data.get("state")
        event_id = attrs.get("event_id")
        if not start_str or not end_str or not loc_type:
            return None
        return _build_calendar_event(start_str, end_str, loc_type, event_id)

    async def async_get_events(
        self,
        hass: HomeAssistant,
        start_date: datetime,
        end_date: datetime,
    ) -> list[CalendarEvent]:
        """Return working location events for the requested date range."""
        try:
            response = await self.coordinator._api_client.async_get_working_location_events(
                self._calendar_id,
                start_date.isoformat(),
                end_date.isoformat(),
            )
        except ClientResponseError as err:
            _LOGGER.error("Error fetching working location events: %s", err)
            return []
        except Exception as err:
            _LOGGER.error("Unexpected error fetching working location events: %s", err)
            return []

        events: list[CalendarEvent] = []
        for raw in response.get("items", []):
            start = raw.get("start", {})
            end = raw.get("end", {})
            start_str = start.get("dateTime") or start.get("date")
            end_str = end.get("dateTime") or end.get("date")
            loc_type = raw.get("workingLocationProperties", {}).get("type", "unknown")
            cal_event = _build_calendar_event(start_str, end_str, loc_type, raw.get("id"))
            if cal_event is not None:
                events.append(cal_event)
        return events


def _build_calendar_event(
    start_str: str | None,
    end_str: str | None,
    loc_type: str,
    event_id: str | None,
) -> CalendarEvent | None:
    """Build a CalendarEvent from raw string start/end and location type."""
    if not start_str or not end_str:
        return None

    start: date | datetime
    end: date | datetime

    if "T" in start_str:
        start_dt = dt_util.parse_datetime(start_str)
        end_dt = dt_util.parse_datetime(end_str)
        if start_dt is None or end_dt is None:
            return None
        start, end = start_dt, end_dt
    else:
        try:
            start = date.fromisoformat(start_str)
            end = date.fromisoformat(end_str)
        except ValueError:
            return None

    summary = _LOCATION_SUMMARIES.get(loc_type, loc_type)
    return CalendarEvent(start=start, end=end, summary=summary, uid=event_id)
