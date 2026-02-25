"""Google Calendar Working Location integration."""

from __future__ import annotations

import logging

from aiohttp import ClientResponseError

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed, ConfigEntryNotReady
from homeassistant.helpers import config_entry_oauth2_flow

from .api import GoogleCalendarApiClient
from .const import (
    CONF_CALENDAR_ID,
    CONF_CONSIDER_NONE_OUTSIDE_HOURS,
    CONF_UPDATE_INTERVAL,
    DEFAULT_CALENDAR_ID,
    DEFAULT_CONSIDER_NONE_OUTSIDE_HOURS,
    DEFAULT_UPDATE_INTERVAL,
    DOMAIN,
)
from .coordinator import WorkingLocationCoordinator

_LOGGER = logging.getLogger(__name__)

PLATFORMS = ["sensor"]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Google Calendar Working Location from a config entry."""
    implementation = (
        await config_entry_oauth2_flow.async_get_config_entry_implementation(
            hass, entry
        )
    )

    session = config_entry_oauth2_flow.OAuth2Session(hass, entry, implementation)

    # Validate that we can get a valid token before proceeding.
    try:
        await session.async_ensure_token_valid()
    except ClientResponseError as err:
        if err.status == 401:
            raise ConfigEntryAuthFailed(
                "Google Calendar credentials are invalid or have been revoked"
            ) from err
        raise ConfigEntryNotReady(
            f"Could not connect to Google Calendar API: {err}"
        ) from err
    except Exception as err:
        raise ConfigEntryNotReady(
            f"Unexpected error validating Google Calendar token: {err}"
        ) from err

    api_client = GoogleCalendarApiClient(session)

    options = entry.options
    calendar_id = options.get(CONF_CALENDAR_ID, DEFAULT_CALENDAR_ID)
    update_interval = options.get(CONF_UPDATE_INTERVAL, DEFAULT_UPDATE_INTERVAL)
    consider_none = options.get(
        CONF_CONSIDER_NONE_OUTSIDE_HOURS, DEFAULT_CONSIDER_NONE_OUTSIDE_HOURS
    )

    coordinator = WorkingLocationCoordinator(
        hass,
        api_client,
        calendar_id,
        update_interval,
        consider_none,
    )

    # Perform initial data fetch; raises ConfigEntryNotReady on failure.
    await coordinator.async_config_entry_first_refresh()

    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = coordinator

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    # Reload the entry whenever the user changes options.
    entry.async_on_unload(entry.add_update_listener(_async_reload_entry))

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id, None)
    return unload_ok


async def _async_reload_entry(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Reload the config entry when options are updated."""
    await hass.config_entries.async_reload(entry.entry_id)
