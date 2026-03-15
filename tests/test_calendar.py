"""Tests for the calendar platform."""

from __future__ import annotations

import pytest
from datetime import date, datetime, timezone, timedelta
from unittest.mock import AsyncMock, MagicMock

from custom_components.working_location.calendar import (
    WorkingLocationCalendar,
    _build_calendar_event,
)
from custom_components.working_location.coordinator import _deduplicate_by_day


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_coordinator(data=None):
    coord = MagicMock()
    coord.data = data
    coord._api_client = MagicMock()
    return coord


def _make_entry(entry_id="test_entry", calendar_id="primary"):
    entry = MagicMock()
    entry.entry_id = entry_id
    entry.options = {"calendar_id": calendar_id}
    return entry


def _make_calendar(data=None, calendar_id="primary"):
    coord = _make_coordinator(data)
    entry = _make_entry(calendar_id=calendar_id)
    cal = WorkingLocationCalendar.__new__(WorkingLocationCalendar)
    cal.coordinator = coord
    cal._calendar_id = calendar_id
    cal._attr_unique_id = f"{entry.entry_id}_working_location_cal"
    return cal


# ---------------------------------------------------------------------------
# _deduplicate_by_day
# ---------------------------------------------------------------------------

def _raw(date_str, recurring=False, event_type="homeOffice", event_id="ev"):
    event = {
        "id": event_id,
        "start": {"date": date_str},
        "end": {"date": date_str},
        "workingLocationProperties": {"type": event_type},
    }
    if recurring:
        event["recurringEventId"] = "parent123"
    return event


def test_deduplicate_keeps_standalone_over_recurring():
    recurring = _raw("2026-03-14", recurring=True, event_type="homeOffice", event_id="rec")
    standalone = _raw("2026-03-14", recurring=False, event_type="officeLocation", event_id="std")
    result = _deduplicate_by_day([recurring, standalone])
    assert len(result) == 1
    assert result[0]["id"] == "std"


def test_deduplicate_keeps_recurring_when_no_standalone():
    recurring = _raw("2026-03-14", recurring=True, event_id="rec")
    result = _deduplicate_by_day([recurring])
    assert len(result) == 1
    assert result[0]["id"] == "rec"


def test_deduplicate_preserves_split_day_standalones():
    # Two standalone events on the same day (genuine split) — both kept
    a = _raw("2026-03-14", recurring=False, event_id="a")
    b = _raw("2026-03-14", recurring=False, event_id="b")
    result = _deduplicate_by_day([a, b])
    assert len(result) == 2


def test_deduplicate_across_multiple_days():
    # Day 1: recurring + standalone → keep standalone
    # Day 2: only recurring → keep it
    day1_rec = _raw("2026-03-14", recurring=True, event_id="d1rec")
    day1_std = _raw("2026-03-14", recurring=False, event_type="officeLocation", event_id="d1std")
    day2_rec = _raw("2026-03-15", recurring=True, event_id="d2rec")
    result = _deduplicate_by_day([day1_rec, day1_std, day2_rec])
    assert len(result) == 2
    ids = {e["id"] for e in result}
    assert ids == {"d1std", "d2rec"}


def test_deduplicate_preserves_order():
    events = [_raw(f"2026-03-{d:02d}", event_id=f"ev{d}") for d in range(14, 18)]
    result = _deduplicate_by_day(events)
    dates = [e["start"]["date"] for e in result]
    assert dates == sorted(dates)


# ---------------------------------------------------------------------------
# _build_calendar_event
# ---------------------------------------------------------------------------

def test_build_calendar_event_timed():
    ev = _build_calendar_event(
        "2026-03-14T09:00:00+00:00",
        "2026-03-14T17:00:00+00:00",
        "homeOffice",
        "abc123",
    )
    assert ev is not None
    assert isinstance(ev.start, datetime)
    assert ev.summary == "Working from Home"
    assert ev.uid == "abc123"


def test_build_calendar_event_allday():
    ev = _build_calendar_event("2026-03-14", "2026-03-15", "officeLocation", "xyz")
    assert ev is not None
    assert isinstance(ev.start, date)
    assert not isinstance(ev.start, datetime)
    assert ev.summary == "Working from Office"


def test_build_calendar_event_unknown_type():
    assert _build_calendar_event("2026-03-14", "2026-03-15", "someNewType", None) is None


def test_build_calendar_event_none_type():
    assert _build_calendar_event("2026-03-14", "2026-03-15", "none", None) is None


def test_build_calendar_event_none_inputs():
    assert _build_calendar_event(None, "2026-03-14", "homeOffice", None) is None
    assert _build_calendar_event("2026-03-14", None, "homeOffice", None) is None


def test_build_calendar_event_invalid_date():
    assert _build_calendar_event("not-a-date", "also-bad", "homeOffice", None) is None


def test_build_calendar_event_invalid_datetime():
    # Has 'T' but is not a valid datetime
    assert _build_calendar_event("2026-03-14Tbadtime", "2026-03-14T17:00:00+00:00", "homeOffice", None) is None


# ---------------------------------------------------------------------------
# WorkingLocationCalendar.event property
# ---------------------------------------------------------------------------

def test_event_property_timed():
    data = {
        "state": "homeOffice",
        "attributes": {
            "start": "2026-03-14T09:00:00+00:00",
            "end": "2026-03-14T17:00:00+00:00",
            "event_id": "ev1",
        },
    }
    cal = _make_calendar(data)
    ev = cal.event
    assert ev is not None
    assert ev.summary == "Working from Home"
    assert ev.uid == "ev1"


def test_event_property_no_data():
    cal = _make_calendar(data=None)
    assert cal.event is None


def test_event_property_no_start_end():
    # STATE_NONE returns no start/end in attributes
    data = {"state": "none", "attributes": {"calendar_id": "primary"}}
    cal = _make_calendar(data)
    assert cal.event is None


# ---------------------------------------------------------------------------
# WorkingLocationCalendar.async_get_events
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_async_get_events_returns_events():
    cal = _make_calendar()
    api_response = {
        "items": [
            {
                "id": "ev1",
                "start": {"dateTime": "2026-03-14T09:00:00+00:00"},
                "end": {"dateTime": "2026-03-14T17:00:00+00:00"},
                "workingLocationProperties": {"type": "homeOffice"},
            },
            {
                "id": "ev2",
                "start": {"date": "2026-03-15"},
                "end": {"date": "2026-03-16"},
                "workingLocationProperties": {"type": "officeLocation"},
            },
        ]
    }
    cal.coordinator._api_client.async_get_working_location_events = AsyncMock(
        return_value=api_response
    )

    start = datetime(2026, 3, 14, tzinfo=timezone.utc)
    end = datetime(2026, 3, 16, tzinfo=timezone.utc)
    events = await cal.async_get_events(None, start, end)

    assert len(events) == 2
    assert events[0].summary == "Working from Home"
    assert events[1].summary == "Working from Office"


@pytest.mark.asyncio
async def test_async_get_events_filters_none_and_unknown():
    cal = _make_calendar()
    api_response = {
        "items": [
            {
                "id": "ev1",
                "start": {"date": "2026-03-14"},
                "end": {"date": "2026-03-15"},
                "workingLocationProperties": {"type": "none"},
            },
            {
                "id": "ev2",
                "start": {"date": "2026-03-15"},
                "end": {"date": "2026-03-16"},
                "workingLocationProperties": {"type": "someUnknownType"},
            },
            {
                "id": "ev3",
                "start": {"date": "2026-03-16"},
                "end": {"date": "2026-03-17"},
                "workingLocationProperties": {"type": "customLocation"},
            },
        ]
    }
    cal.coordinator._api_client.async_get_working_location_events = AsyncMock(
        return_value=api_response
    )
    events = await cal.async_get_events(None, datetime(2026, 3, 14), datetime(2026, 3, 17))
    assert len(events) == 1
    assert events[0].summary == "Working from Elsewhere"


@pytest.mark.asyncio
async def test_async_get_events_empty():
    cal = _make_calendar()
    cal.coordinator._api_client.async_get_working_location_events = AsyncMock(
        return_value={"items": []}
    )
    events = await cal.async_get_events(None, datetime.now(), datetime.now())
    assert events == []


@pytest.mark.asyncio
async def test_async_get_events_api_error():
    from aiohttp import ClientResponseError, RequestInfo
    from unittest.mock import MagicMock
    from yarl import URL
    request_info = RequestInfo(URL("https://example.com"), "GET", {}, URL("https://example.com"))
    cal = _make_calendar()
    cal.coordinator._api_client.async_get_working_location_events = AsyncMock(
        side_effect=ClientResponseError(request_info, None, status=500)
    )
    events = await cal.async_get_events(None, datetime.now(), datetime.now())
    assert events == []


@pytest.mark.asyncio
async def test_async_get_events_unexpected_error():
    cal = _make_calendar()
    cal.coordinator._api_client.async_get_working_location_events = AsyncMock(
        side_effect=RuntimeError("boom")
    )
    events = await cal.async_get_events(None, datetime.now(), datetime.now())
    assert events == []
