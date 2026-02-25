"""Sensor platform for Google Calendar Working Location."""

from __future__ import annotations

import logging
from typing import Any

from homeassistant.components.sensor import SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DEFAULT_CALENDAR_ID, CONF_CALENDAR_ID, DOMAIN
from .coordinator import WorkingLocationCoordinator

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the working location sensor from a config entry."""
    coordinator: WorkingLocationCoordinator = hass.data[DOMAIN][entry.entry_id]
    calendar_id = entry.options.get(CONF_CALENDAR_ID, DEFAULT_CALENDAR_ID)
    async_add_entities([WorkingLocationSensor(coordinator, entry, calendar_id)])


class WorkingLocationSensor(CoordinatorEntity[WorkingLocationCoordinator], SensorEntity):
    """Sensor exposing the user's Google Calendar working location for today."""

    _attr_icon = "mdi:briefcase-clock"
    _attr_has_entity_name = True
    _attr_name = "Working Location"

    def __init__(
        self,
        coordinator: WorkingLocationCoordinator,
        entry: ConfigEntry,
        calendar_id: str,
    ) -> None:
        """Initialise the sensor."""
        super().__init__(coordinator)
        self._calendar_id = calendar_id
        # Unique ID scoped to this config entry so multiple accounts could coexist
        self._attr_unique_id = f"{entry.entry_id}_working_location"

    @property
    def native_value(self) -> str | None:
        """Return the current working location state."""
        if self.coordinator.data is None:
            return None
        return self.coordinator.data.get("state")

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return working location details as state attributes."""
        if self.coordinator.data is None:
            return {}
        return self.coordinator.data.get("attributes", {})

    @property
    def available(self) -> bool:
        """Return False when the last coordinator update failed."""
        return self.coordinator.last_update_success and self.coordinator.data is not None
