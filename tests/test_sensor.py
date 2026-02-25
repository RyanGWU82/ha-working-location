"""Tests for sensor.py — WorkingLocationSensor."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from custom_components.working_location.sensor import WorkingLocationSensor
from custom_components.working_location.const import (
    STATE_HOME_OFFICE,
    STATE_OFFICE_LOCATION,
    STATE_NONE,
    STATE_UNKNOWN,
)


def _make_coordinator(state: str, attrs: dict, last_update_success: bool = True):
    """Build a minimal mock coordinator with the given data."""
    coord = MagicMock()
    coord.data = {"state": state, "attributes": attrs}
    coord.last_update_success = last_update_success
    return coord


def _make_entry(entry_id: str = "test_entry_id"):
    entry = MagicMock()
    entry.entry_id = entry_id
    return entry


def _make_sensor(state=STATE_HOME_OFFICE, attrs=None, last_update_success=True, entry_id="eid"):
    if attrs is None:
        attrs = {"calendar_id": "primary"}
    coordinator = _make_coordinator(state, attrs, last_update_success)
    entry = _make_entry(entry_id)
    return WorkingLocationSensor(coordinator, entry, "primary")


class TestWorkingLocationSensorValue:
    """Tests for native_value and extra_state_attributes."""

    def test_native_value_reflects_coordinator_state(self):
        sensor = _make_sensor(state=STATE_HOME_OFFICE)
        assert sensor.native_value == STATE_HOME_OFFICE

    def test_native_value_office_location(self):
        sensor = _make_sensor(state=STATE_OFFICE_LOCATION)
        assert sensor.native_value == STATE_OFFICE_LOCATION

    def test_native_value_none_state(self):
        sensor = _make_sensor(state=STATE_NONE)
        assert sensor.native_value == STATE_NONE

    def test_native_value_unknown_state(self):
        sensor = _make_sensor(state=STATE_UNKNOWN)
        assert sensor.native_value == STATE_UNKNOWN

    def test_native_value_is_none_when_coordinator_data_is_none(self):
        coord = MagicMock()
        coord.data = None
        coord.last_update_success = True
        sensor = WorkingLocationSensor(coord, _make_entry(), "primary")
        assert sensor.native_value is None

    def test_extra_state_attributes_returns_coordinator_attributes(self):
        attrs = {
            "calendar_id": "primary",
            "event_id": "evt123",
            "type": "homeOffice",
            "homeOffice": {},
            "start": "2024-01-15",
            "end": "2024-01-16",
        }
        sensor = _make_sensor(state=STATE_HOME_OFFICE, attrs=attrs)
        result = sensor.extra_state_attributes
        assert result == attrs

    def test_extra_state_attributes_empty_when_coordinator_data_is_none(self):
        coord = MagicMock()
        coord.data = None
        coord.last_update_success = True
        sensor = WorkingLocationSensor(coord, _make_entry(), "primary")
        assert sensor.extra_state_attributes == {}

    def test_extra_state_attributes_empty_dict_when_attributes_key_missing(self):
        coord = MagicMock()
        coord.data = {"state": STATE_NONE}  # no "attributes" key
        coord.last_update_success = True
        sensor = WorkingLocationSensor(coord, _make_entry(), "primary")
        assert sensor.extra_state_attributes == {}


class TestWorkingLocationSensorAvailability:
    """Tests for the available property."""

    def test_available_true_when_update_succeeded_and_data_present(self):
        sensor = _make_sensor(last_update_success=True)
        assert sensor.available is True

    def test_available_false_when_last_update_failed(self):
        sensor = _make_sensor(last_update_success=False)
        assert sensor.available is False

    def test_available_false_when_coordinator_data_is_none(self):
        coord = MagicMock()
        coord.data = None
        coord.last_update_success = True
        sensor = WorkingLocationSensor(coord, _make_entry(), "primary")
        assert sensor.available is False

    def test_available_false_when_both_conditions_fail(self):
        coord = MagicMock()
        coord.data = None
        coord.last_update_success = False
        sensor = WorkingLocationSensor(coord, _make_entry(), "primary")
        assert sensor.available is False


class TestWorkingLocationSensorIdentity:
    """Tests for entity identity and static attributes."""

    def test_unique_id_uses_entry_id(self):
        sensor = _make_sensor(entry_id="my_unique_entry")
        assert sensor._attr_unique_id == "my_unique_entry_working_location"

    def test_unique_id_different_entries_differ(self):
        s1 = _make_sensor(entry_id="entry_a")
        s2 = _make_sensor(entry_id="entry_b")
        assert s1._attr_unique_id != s2._attr_unique_id

    def test_entity_name(self):
        sensor = _make_sensor()
        assert sensor._attr_name == "Working Location"

    def test_has_entity_name_flag(self):
        sensor = _make_sensor()
        assert sensor._attr_has_entity_name is True

    def test_icon(self):
        sensor = _make_sensor()
        assert sensor._attr_icon == "mdi:briefcase-clock"
