"""Thin Google Calendar API client for the Working Location integration."""

from __future__ import annotations

import logging
from typing import Any

from aiohttp import ClientResponseError

from .const import CALENDAR_API_URL

_LOGGER = logging.getLogger(__name__)


class GoogleCalendarApiClient:
    """Minimal wrapper around the Google Calendar Events.list endpoint."""

    def __init__(self, oauth_session: Any) -> None:
        """Initialise with an HA OAuth2Session."""
        self._session = oauth_session

    async def async_get_working_location_events(
        self,
        calendar_id: str,
        time_min: str,
        time_max: str,
    ) -> dict[str, Any]:
        """Fetch workingLocation events for the given calendar and time window.

        Args:
            calendar_id: Google Calendar ID (e.g. ``"primary"``).
            time_min: RFC3339 lower bound (inclusive), e.g. today 00:00 local.
            time_max: RFC3339 upper bound (exclusive), e.g. tomorrow 00:00 local.

        Returns:
            The raw JSON response dict from the Calendar API, or raises on
            HTTP / auth errors.

        Raises:
            aiohttp.ClientResponseError: on non-2xx HTTP responses.
        """
        url = CALENDAR_API_URL.format(calendar_id=calendar_id)
        params = {
            "timeMin": time_min,
            "timeMax": time_max,
            "singleEvents": "true",
            "orderBy": "startTime",
            "eventTypes": "workingLocation",
        }

        _LOGGER.debug(
            "Fetching working location events for calendar %s [%s, %s]",
            calendar_id,
            time_min,
            time_max,
        )

        resp = await self._session.async_request("GET", url, params=params)
        resp.raise_for_status()
        return await resp.json()
