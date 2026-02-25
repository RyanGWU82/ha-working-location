"""
Stub the homeassistant package so the integration can be imported and tested
without a real HA installation.  All sys.modules patching happens at module
load time (before any test file is imported by pytest).
"""

from __future__ import annotations

import sys
import types
from datetime import datetime, timezone, timedelta
from unittest.mock import MagicMock


# ---------------------------------------------------------------------------
# Stub exception classes (mirror the real HA names used in coordinator.py)
# ---------------------------------------------------------------------------

class UpdateFailed(Exception):
    """Stub for homeassistant.helpers.update_coordinator.UpdateFailed."""


class ConfigEntryAuthFailed(Exception):
    """Stub for homeassistant.exceptions.ConfigEntryAuthFailed."""


class ConfigEntryNotReady(Exception):
    """Stub for homeassistant.exceptions.ConfigEntryNotReady."""


# ---------------------------------------------------------------------------
# Stub base classes
# ---------------------------------------------------------------------------

class StubDataUpdateCoordinator:
    """Minimal stand-in for DataUpdateCoordinator."""

    # Allow DataUpdateCoordinator[T] subscript syntax used in class definitions.
    def __class_getitem__(cls, _item):
        return cls

    def __init__(self, hass, logger, *, name, update_interval, **kwargs):
        self.hass = hass
        self.data = None
        self.last_update_success = True
        self.update_interval = update_interval


class StubCoordinatorEntity:
    """Minimal stand-in for CoordinatorEntity."""

    def __class_getitem__(cls, _item):
        return cls

    def __init__(self, coordinator):
        self.coordinator = coordinator


class StubSensorEntity:
    """Minimal stand-in for SensorEntity."""


# ---------------------------------------------------------------------------
# Stub dt_util (used as a module attribute, not a real module)
# ---------------------------------------------------------------------------

class StubDtUtil:
    """Stand-in for homeassistant.util.dt accessed as ``dt_util``."""

    @staticmethod
    def parse_datetime(s: str) -> datetime | None:
        """Parse RFC3339 datetime string; handles Z suffix."""
        if not s:
            return None
        try:
            return datetime.fromisoformat(s.replace("Z", "+00:00"))
        except (ValueError, AttributeError):
            return None

    @staticmethod
    def now() -> datetime:
        return datetime.now(timezone.utc)


# ---------------------------------------------------------------------------
# Build fake HA module tree and register in sys.modules
# ---------------------------------------------------------------------------

def _mod(name: str, **attrs) -> types.ModuleType:
    m = types.ModuleType(name)
    for k, v in attrs.items():
        setattr(m, k, v)
    return m


_util_mod = _mod("homeassistant.util", dt=StubDtUtil)

_HA_MODULES: dict[str, object] = {
    "homeassistant": MagicMock(),
    "homeassistant.config_entries": MagicMock(),
    "homeassistant.core": MagicMock(),
    "homeassistant.exceptions": _mod(
        "homeassistant.exceptions",
        ConfigEntryAuthFailed=ConfigEntryAuthFailed,
        ConfigEntryNotReady=ConfigEntryNotReady,
    ),
    "homeassistant.helpers": MagicMock(),
    "homeassistant.helpers.update_coordinator": _mod(
        "homeassistant.helpers.update_coordinator",
        DataUpdateCoordinator=StubDataUpdateCoordinator,
        UpdateFailed=UpdateFailed,
        CoordinatorEntity=StubCoordinatorEntity,
    ),
    "homeassistant.helpers.entity_platform": MagicMock(),
    "homeassistant.helpers.config_entry_oauth2_flow": MagicMock(),
    "homeassistant.components": MagicMock(),
    "homeassistant.components.sensor": _mod(
        "homeassistant.components.sensor",
        SensorEntity=StubSensorEntity,
    ),
    "homeassistant.util": _util_mod,
    # Make `from homeassistant.util import dt as dt_util` resolve to StubDtUtil
    "homeassistant.util.dt": StubDtUtil,
}

for _name, _module in _HA_MODULES.items():
    sys.modules[_name] = _module  # type: ignore[assignment]
