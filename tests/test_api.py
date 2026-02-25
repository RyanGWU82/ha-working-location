"""Tests for api.py — GoogleCalendarApiClient."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, call

import pytest

from custom_components.working_location.api import GoogleCalendarApiClient
from custom_components.working_location.const import CALENDAR_API_URL


class TestGoogleCalendarApiClient:
    """Tests for GoogleCalendarApiClient.async_get_working_location_events."""

    def _make_client(self, response_data: dict | None = None, raise_error=None):
        """Return a client whose session produces a mock response."""
        mock_resp = MagicMock()
        mock_resp.raise_for_status = MagicMock(
            side_effect=raise_error if raise_error else None
        )
        mock_resp.json = AsyncMock(return_value=response_data or {"items": []})

        mock_session = AsyncMock()
        mock_session.async_request.return_value = mock_resp

        return GoogleCalendarApiClient(mock_session), mock_session, mock_resp

    async def test_returns_parsed_json(self):
        payload = {"items": [{"id": "abc"}]}
        client, _, _ = self._make_client(payload)
        result = await client.async_get_working_location_events(
            "primary", "2024-01-15T00:00:00+00:00", "2024-01-16T00:00:00+00:00"
        )
        assert result == payload

    async def test_url_contains_calendar_id(self):
        client, session, _ = self._make_client()
        await client.async_get_working_location_events(
            "my_calendar", "2024-01-15T00:00:00+00:00", "2024-01-16T00:00:00+00:00"
        )
        call_url = session.async_request.call_args[0][1]
        assert "my_calendar" in call_url
        assert call_url == CALENDAR_API_URL.format(calendar_id="my_calendar")

    async def test_http_method_is_get(self):
        client, session, _ = self._make_client()
        await client.async_get_working_location_events(
            "primary", "2024-01-15T00:00:00+00:00", "2024-01-16T00:00:00+00:00"
        )
        assert session.async_request.call_args[0][0] == "GET"

    async def test_required_query_params_present(self):
        client, session, _ = self._make_client()
        time_min = "2024-01-15T00:00:00+00:00"
        time_max = "2024-01-16T00:00:00+00:00"

        await client.async_get_working_location_events("primary", time_min, time_max)

        params = session.async_request.call_args[1]["params"]
        assert params["timeMin"] == time_min
        assert params["timeMax"] == time_max
        assert params["singleEvents"] == "true"
        assert params["orderBy"] == "startTime"
        assert params["eventTypes"] == "workingLocation"

    async def test_raise_for_status_is_called(self):
        client, _, mock_resp = self._make_client()
        await client.async_get_working_location_events(
            "primary", "2024-01-15T00:00:00+00:00", "2024-01-16T00:00:00+00:00"
        )
        mock_resp.raise_for_status.assert_called_once()

    async def test_http_error_propagates(self):
        from aiohttp import ClientResponseError

        class _FakeError(ClientResponseError):
            def __init__(self):
                self.status = 403
                self.message = "Forbidden"
                self.headers = None
                self.history = ()
                self.request_info = MagicMock()

        client, _, _ = self._make_client(raise_error=_FakeError())

        with pytest.raises(ClientResponseError):
            await client.async_get_working_location_events(
                "primary", "2024-01-15T00:00:00+00:00", "2024-01-16T00:00:00+00:00"
            )

    async def test_primary_calendar_id_in_url(self):
        client, session, _ = self._make_client()
        await client.async_get_working_location_events(
            "primary", "2024-01-15T00:00:00+00:00", "2024-01-16T00:00:00+00:00"
        )
        call_url = session.async_request.call_args[0][1]
        assert call_url == CALENDAR_API_URL.format(calendar_id="primary")
