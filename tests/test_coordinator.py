"""Tests for coordinator.py — parsing helpers and WorkingLocationCoordinator."""

from __future__ import annotations

from datetime import datetime, timezone, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# conftest.py has already patched sys.modules before these imports run.
from custom_components.working_location.coordinator import (
    WorkingLocationCoordinator,
    _event_covers_now,
    _extract_state_and_attrs,
    _parse_events,
    ConfigEntryAuthFailed,
    UpdateFailed,
)
from custom_components.working_location.const import (
    STATE_CUSTOM_LOCATION,
    STATE_HOME_OFFICE,
    STATE_NONE,
    STATE_OFFICE_LOCATION,
    STATE_UNKNOWN,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

UTC = timezone.utc

_NOW = datetime(2024, 1, 15, 14, 30, tzinfo=UTC)  # 14:30 UTC on 2024-01-15


def _dt(hour: int, minute: int = 0) -> str:
    """Return a UTC ISO-8601 dateTime string for 2024-01-15 at the given time."""
    return f"2024-01-15T{hour:02d}:{minute:02d}:00+00:00"


def _all_day_event(wlp: dict) -> dict:
    return {
        "id": "evt-allday",
        "start": {"date": "2024-01-15"},
        "end": {"date": "2024-01-16"},
        "workingLocationProperties": wlp,
    }


def _timed_event(start_hour: int, end_hour: int, wlp: dict, eid: str = "evt") -> dict:
    return {
        "id": eid,
        "start": {"dateTime": _dt(start_hour)},
        "end": {"dateTime": _dt(end_hour)},
        "workingLocationProperties": wlp,
    }


_HOME_WLP = {"type": "homeOffice", "homeOffice": {}}
_OFFICE_WLP = {
    "type": "officeLocation",
    "officeLocation": {
        "buildingId": "B1",
        "floorId": "2",
        "floorSectionId": "East",
        "deskId": "D42",
        "label": "HQ",
    },
}
_CUSTOM_WLP = {"type": "customLocation", "customLocation": {"label": "Café"}}


# ===========================================================================
# _event_covers_now
# ===========================================================================

class TestEventCoversNow:
    """Tests for the _event_covers_now helper."""

    def test_all_day_event_always_covers_now(self):
        event = {"start": {"date": "2024-01-15"}, "end": {"date": "2024-01-16"}}
        assert _event_covers_now(event, _NOW) is True

    def test_timed_event_covers_now_at_midday(self):
        event = {
            "start": {"dateTime": _dt(9)},
            "end": {"dateTime": _dt(17)},
        }
        # _NOW is 14:30 — inside [09:00, 17:00)
        assert _event_covers_now(event, _NOW) is True

    def test_timed_event_start_boundary_is_inclusive(self):
        # now == start → should be True (start <= now < end)
        now = datetime(2024, 1, 15, 9, 0, tzinfo=UTC)
        event = {
            "start": {"dateTime": _dt(9)},
            "end": {"dateTime": _dt(17)},
        }
        assert _event_covers_now(event, now) is True

    def test_timed_event_end_boundary_is_exclusive(self):
        # now == end → should be False (start <= now < end)
        now = datetime(2024, 1, 15, 17, 0, tzinfo=UTC)
        event = {
            "start": {"dateTime": _dt(9)},
            "end": {"dateTime": _dt(17)},
        }
        assert _event_covers_now(event, now) is False

    def test_timed_event_before_start_returns_false(self):
        now = datetime(2024, 1, 15, 8, 0, tzinfo=UTC)
        event = {
            "start": {"dateTime": _dt(9)},
            "end": {"dateTime": _dt(17)},
        }
        assert _event_covers_now(event, now) is False

    def test_timed_event_after_end_returns_false(self):
        now = datetime(2024, 1, 15, 18, 0, tzinfo=UTC)
        event = {
            "start": {"dateTime": _dt(9)},
            "end": {"dateTime": _dt(17)},
        }
        assert _event_covers_now(event, now) is False

    def test_event_with_no_start_returns_false(self):
        event = {}
        assert _event_covers_now(event, _NOW) is False

    def test_timed_event_with_only_start_datetime_returns_false(self):
        # Missing end.dateTime — the condition requires both keys.
        event = {"start": {"dateTime": _dt(9)}, "end": {}}
        assert _event_covers_now(event, _NOW) is False

    def test_timed_event_unparseable_datetime_returns_false(self):
        event = {
            "start": {"dateTime": "not-a-date"},
            "end": {"dateTime": "also-not-a-date"},
        }
        assert _event_covers_now(event, _NOW) is False

    def test_timed_event_with_z_utc_suffix(self):
        # Google Calendar sometimes returns Z instead of +00:00.
        now = datetime(2024, 1, 15, 12, 0, tzinfo=UTC)
        event = {
            "start": {"dateTime": "2024-01-15T09:00:00Z"},
            "end": {"dateTime": "2024-01-15T17:00:00Z"},
        }
        assert _event_covers_now(event, now) is True


# ===========================================================================
# _extract_state_and_attrs
# ===========================================================================

class TestExtractStateAndAttrs:
    """Tests for the _extract_state_and_attrs helper."""

    def test_home_office_state_and_type(self):
        result = _extract_state_and_attrs(_all_day_event(_HOME_WLP), "primary")
        assert result["state"] == STATE_HOME_OFFICE
        assert result["attributes"]["type"] == "homeOffice"

    def test_home_office_raw_value_in_attrs(self):
        result = _extract_state_and_attrs(_all_day_event(_HOME_WLP), "primary")
        assert "homeOffice" in result["attributes"]
        assert result["attributes"]["homeOffice"] == {}

    def test_office_location_state_and_all_fields(self):
        result = _extract_state_and_attrs(_all_day_event(_OFFICE_WLP), "primary")
        attrs = result["attributes"]
        assert result["state"] == STATE_OFFICE_LOCATION
        assert attrs["officeLocation_buildingId"] == "B1"
        assert attrs["officeLocation_floorId"] == "2"
        assert attrs["officeLocation_floorSectionId"] == "East"
        assert attrs["officeLocation_deskId"] == "D42"
        assert attrs["officeLocation_label"] == "HQ"

    def test_office_location_partial_fields_only_present_included(self):
        wlp = {"type": "officeLocation", "officeLocation": {"buildingId": "B2"}}
        result = _extract_state_and_attrs(_all_day_event(wlp), "primary")
        attrs = result["attributes"]
        assert attrs["officeLocation_buildingId"] == "B2"
        assert "officeLocation_floorId" not in attrs
        assert "officeLocation_deskId" not in attrs

    def test_custom_location_with_label(self):
        result = _extract_state_and_attrs(_all_day_event(_CUSTOM_WLP), "primary")
        assert result["state"] == STATE_CUSTOM_LOCATION
        assert result["attributes"]["customLocation_label"] == "Café"

    def test_custom_location_without_label_omits_attribute(self):
        """customLocation_label must be omitted when label is not present."""
        wlp = {"type": "customLocation", "customLocation": {}}
        result = _extract_state_and_attrs(_all_day_event(wlp), "primary")
        assert result["state"] == STATE_CUSTOM_LOCATION
        assert "customLocation_label" not in result["attributes"]

    def test_custom_location_label_none_value_omitted(self):
        """If label key is present but None, it is still included (falsy ≠ absent)."""
        # The spec says omit fields *not present*; a present-but-None label is
        # an edge case we preserve as-is.
        wlp = {"type": "customLocation", "customLocation": {"label": None}}
        result = _extract_state_and_attrs(_all_day_event(wlp), "primary")
        # label key IS present, so customLocation_label should be included
        assert "customLocation_label" in result["attributes"]
        assert result["attributes"]["customLocation_label"] is None

    def test_unknown_type_maps_to_unknown_state(self):
        wlp = {"type": "alienLocation", "alienLocation": {}}
        result = _extract_state_and_attrs(_all_day_event(wlp), "primary")
        assert result["state"] == STATE_UNKNOWN

    def test_unknown_type_includes_raw_wlp(self):
        wlp = {"type": "alienLocation", "raw": "data"}
        result = _extract_state_and_attrs(_all_day_event(wlp), "primary")
        assert result["attributes"]["workingLocationProperties"] == wlp

    def test_missing_type_maps_to_unknown(self):
        wlp = {"homeOffice": {}}  # no 'type' key
        result = _extract_state_and_attrs(_all_day_event(wlp), "primary")
        assert result["state"] == STATE_UNKNOWN

    def test_empty_wlp_maps_to_unknown_without_raw_attr(self):
        # wlp is falsy — raw attr should NOT be added
        result = _extract_state_and_attrs(_all_day_event({}), "primary")
        assert result["state"] == STATE_UNKNOWN
        assert "workingLocationProperties" not in result["attributes"]

    def test_calendar_id_always_in_attrs(self):
        result = _extract_state_and_attrs(_all_day_event(_HOME_WLP), "work_cal")
        assert result["attributes"]["calendar_id"] == "work_cal"

    def test_event_id_in_attrs(self):
        result = _extract_state_and_attrs(_all_day_event(_HOME_WLP), "primary")
        assert result["attributes"]["event_id"] == "evt-allday"

    def test_all_day_event_start_end_format(self):
        result = _extract_state_and_attrs(_all_day_event(_HOME_WLP), "primary")
        attrs = result["attributes"]
        assert attrs["start"] == "2024-01-15"
        assert attrs["end"] == "2024-01-16"

    def test_timed_event_start_end_format(self):
        event = _timed_event(9, 17, _HOME_WLP)
        result = _extract_state_and_attrs(event, "primary")
        attrs = result["attributes"]
        assert attrs["start"] == _dt(9)
        assert attrs["end"] == _dt(17)

    def test_type_attr_absent_when_type_is_none(self):
        # When wlp has no 'type', the 'type' attribute should be absent
        wlp = {}
        result = _extract_state_and_attrs(_all_day_event(wlp), "primary")
        assert "type" not in result["attributes"]


# ===========================================================================
# _parse_events
# ===========================================================================

class TestParseEvents:
    """Tests for the top-level _parse_events dispatcher."""

    def test_empty_events_returns_none_state(self):
        result = _parse_events([], _NOW, "primary", False)
        assert result["state"] == STATE_NONE
        assert result["attributes"]["calendar_id"] == "primary"

    def test_single_all_day_event_is_selected(self):
        events = [_all_day_event(_HOME_WLP)]
        result = _parse_events(events, _NOW, "primary", False)
        assert result["state"] == STATE_HOME_OFFICE

    def test_event_covering_now_is_preferred(self):
        # Two events: [08:00-12:00] (home) and [12:00-18:00] (office)
        # _NOW is 14:30 → inside the second event
        events = [
            _timed_event(8, 12, _HOME_WLP, "e1"),
            _timed_event(12, 18, _OFFICE_WLP, "e2"),
        ]
        result = _parse_events(events, _NOW, "primary", False)
        assert result["state"] == STATE_OFFICE_LOCATION
        assert result["attributes"]["event_id"] == "e2"

    def test_earliest_event_selected_when_none_cover_now(self):
        # Two future events, neither covers 14:30
        # _NOW is 14:30 → both events are after it: [15:00-16:00] and [16:00-17:00]
        now = datetime(2024, 1, 15, 14, 30, tzinfo=UTC)
        events = [
            _timed_event(15, 16, _HOME_WLP, "e1"),
            _timed_event(16, 17, _OFFICE_WLP, "e2"),
        ]
        result = _parse_events(events, now, "primary", False)
        # Neither covers now → fall back to first (earliest) = e1 = homeOffice
        assert result["state"] == STATE_HOME_OFFICE
        assert result["attributes"]["event_id"] == "e1"

    def test_consider_none_outside_hours_true_returns_none_when_no_current_event(self):
        now = datetime(2024, 1, 15, 20, 0, tzinfo=UTC)  # 20:00, after hours
        events = [_timed_event(9, 17, _HOME_WLP)]  # event ended
        result = _parse_events(events, now, "primary", consider_none_outside_hours=True)
        assert result["state"] == STATE_NONE

    def test_consider_none_outside_hours_false_uses_earliest(self):
        now = datetime(2024, 1, 15, 20, 0, tzinfo=UTC)
        events = [_timed_event(9, 17, _HOME_WLP)]
        result = _parse_events(events, now, "primary", consider_none_outside_hours=False)
        assert result["state"] == STATE_HOME_OFFICE

    def test_consider_none_outside_hours_true_with_covering_event_uses_it(self):
        # An event covers now; consider_none flag should not suppress it
        events = [_timed_event(9, 17, _OFFICE_WLP)]
        result = _parse_events(events, _NOW, "primary", consider_none_outside_hours=True)
        assert result["state"] == STATE_OFFICE_LOCATION

    def test_calendar_id_propagated_to_attrs(self):
        events = [_all_day_event(_HOME_WLP)]
        result = _parse_events(events, _NOW, "work_cal", False)
        assert result["attributes"]["calendar_id"] == "work_cal"

    def test_calendar_id_in_empty_events_attrs(self):
        result = _parse_events([], _NOW, "work_cal", False)
        assert result["attributes"]["calendar_id"] == "work_cal"

    def test_all_day_event_always_counts_as_covering_now(self):
        # Verify that an all-day event is preferred over a timed fallback
        now = datetime(2024, 1, 15, 22, 0, tzinfo=UTC)  # late evening
        events = [
            _all_day_event(_HOME_WLP),  # covers all day
        ]
        result = _parse_events(events, now, "primary", consider_none_outside_hours=True)
        # All-day event covers now, so state should not be none
        assert result["state"] == STATE_HOME_OFFICE

    def test_custom_location_state_and_label(self):
        events = [_all_day_event(_CUSTOM_WLP)]
        result = _parse_events(events, _NOW, "primary", False)
        assert result["state"] == STATE_CUSTOM_LOCATION
        assert result["attributes"]["customLocation_label"] == "Café"


# ===========================================================================
# WorkingLocationCoordinator._async_update_data
# ===========================================================================

class TestCoordinatorUpdateData:
    """Tests for the coordinator's async update method."""

    def _make_coordinator(self, mock_client, consider_none=False):
        return WorkingLocationCoordinator(
            hass=MagicMock(),
            api_client=mock_client,
            calendar_id="primary",
            update_interval_minutes=5,
            consider_none_outside_hours=consider_none,
        )

    def _patch_dt_util(self, now: datetime):
        """Return a patch context manager that fixes dt_util.now() to *now*."""
        return patch(
            "custom_components.working_location.coordinator.dt_util",
            **{
                "now.return_value": now,
                "parse_datetime.side_effect": lambda s: datetime.fromisoformat(
                    s.replace("Z", "+00:00")
                ),
            },
        )

    async def test_success_returns_parsed_data(self):
        mock_client = AsyncMock()
        mock_client.async_get_working_location_events.return_value = {
            "items": [_all_day_event(_HOME_WLP)]
        }
        coord = self._make_coordinator(mock_client)

        with self._patch_dt_util(_NOW):
            result = await coord._async_update_data()

        assert result["state"] == STATE_HOME_OFFICE
        assert result["attributes"]["calendar_id"] == "primary"

    async def test_time_window_spans_today_midnight_to_midnight(self):
        mock_client = AsyncMock()
        mock_client.async_get_working_location_events.return_value = {"items": []}
        coord = self._make_coordinator(mock_client)

        now = datetime(2024, 1, 15, 14, 30, tzinfo=timezone(timedelta(hours=5, minutes=30)))
        with self._patch_dt_util(now):
            await coord._async_update_data()

        _, call_kwargs = mock_client.async_get_working_location_events.call_args
        # positional args: calendar_id, time_min, time_max
        call_args = mock_client.async_get_working_location_events.call_args[0]
        time_min = call_args[1]
        time_max = call_args[2]

        # time_min should be today at midnight in the local tz (+05:30)
        assert time_min.startswith("2024-01-15T00:00:00")
        # time_max should be tomorrow midnight
        assert time_max.startswith("2024-01-16T00:00:00")

    async def test_401_raises_config_entry_auth_failed(self):
        from aiohttp import ClientResponseError

        class _Err401(ClientResponseError):
            def __init__(self):
                self.status = 401
                self.message = "Unauthorized"
                self.headers = None
                self.history = ()
                self.request_info = MagicMock()

        mock_client = AsyncMock()
        mock_client.async_get_working_location_events.side_effect = _Err401()
        coord = self._make_coordinator(mock_client)

        with self._patch_dt_util(_NOW):
            with pytest.raises(ConfigEntryAuthFailed):
                await coord._async_update_data()

    async def test_non_401_http_error_raises_update_failed(self):
        from aiohttp import ClientResponseError

        class _Err500(ClientResponseError):
            def __init__(self):
                self.status = 500
                self.message = "Server Error"
                self.headers = None
                self.history = ()
                self.request_info = MagicMock()

        mock_client = AsyncMock()
        mock_client.async_get_working_location_events.side_effect = _Err500()
        coord = self._make_coordinator(mock_client)

        with self._patch_dt_util(_NOW):
            with pytest.raises(UpdateFailed):
                await coord._async_update_data()

    async def test_generic_exception_raises_update_failed(self):
        mock_client = AsyncMock()
        mock_client.async_get_working_location_events.side_effect = RuntimeError("network down")
        coord = self._make_coordinator(mock_client)

        with self._patch_dt_util(_NOW):
            with pytest.raises(UpdateFailed):
                await coord._async_update_data()

    async def test_empty_response_returns_none_state(self):
        mock_client = AsyncMock()
        mock_client.async_get_working_location_events.return_value = {"items": []}
        coord = self._make_coordinator(mock_client)

        with self._patch_dt_util(_NOW):
            result = await coord._async_update_data()

        assert result["state"] == STATE_NONE

    async def test_missing_items_key_treated_as_empty(self):
        mock_client = AsyncMock()
        mock_client.async_get_working_location_events.return_value = {}  # no "items"
        coord = self._make_coordinator(mock_client)

        with self._patch_dt_util(_NOW):
            result = await coord._async_update_data()

        assert result["state"] == STATE_NONE

    async def test_calendar_id_passed_to_api(self):
        mock_client = AsyncMock()
        mock_client.async_get_working_location_events.return_value = {"items": []}
        coord = WorkingLocationCoordinator(
            hass=MagicMock(),
            api_client=mock_client,
            calendar_id="my_work_cal",
            update_interval_minutes=5,
            consider_none_outside_hours=False,
        )

        with self._patch_dt_util(_NOW):
            await coord._async_update_data()

        call_args = mock_client.async_get_working_location_events.call_args[0]
        assert call_args[0] == "my_work_cal"
