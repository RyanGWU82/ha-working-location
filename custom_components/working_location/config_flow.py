"""Config flow and options flow for Google Calendar Working Location."""

from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol

from homeassistant.config_entries import ConfigEntry, OptionsFlow
from homeassistant.helpers import config_entry_oauth2_flow

from .const import (
    CONF_CALENDAR_ID,
    CONF_CONSIDER_NONE_OUTSIDE_HOURS,
    CONF_UPDATE_INTERVAL,
    DEFAULT_CALENDAR_ID,
    DEFAULT_CONSIDER_NONE_OUTSIDE_HOURS,
    DEFAULT_UPDATE_INTERVAL,
    DOMAIN,
    OAUTH2_SCOPE,
)

_LOGGER = logging.getLogger(__name__)


class WorkingLocationFlowHandler(
    config_entry_oauth2_flow.AbstractOAuth2FlowHandler,
    domain=DOMAIN,
):
    """Handle the OAuth2 config flow for Working Location."""

    DOMAIN = DOMAIN
    VERSION = 1

    @property
    def logger(self) -> logging.Logger:
        """Return the logger."""
        return _LOGGER

    @property
    def extra_authorize_data(self) -> dict[str, str]:
        """Return extra parameters to pass to the authorize URL."""
        return {"scope": OAUTH2_SCOPE}

    async def async_oauth_create_entry(self, data: dict[str, Any]) -> Any:
        """Create the config entry after successful OAuth."""
        return self.async_create_entry(
            title="Google Calendar Working Location",
            data=data,
        )

    @staticmethod
    def async_get_options_flow(config_entry: ConfigEntry) -> WorkingLocationOptionsFlow:
        """Return the options flow handler."""
        return WorkingLocationOptionsFlow(config_entry)


class WorkingLocationOptionsFlow(OptionsFlow):
    """Handle options for Working Location (calendar ID, update interval, etc.)."""

    def __init__(self, config_entry: ConfigEntry) -> None:
        """Initialise the options flow."""
        self._config_entry = config_entry

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> Any:
        """Show the options form."""
        current = self._config_entry.options

        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)

        schema = vol.Schema(
            {
                vol.Optional(
                    CONF_CALENDAR_ID,
                    default=current.get(CONF_CALENDAR_ID, DEFAULT_CALENDAR_ID),
                ): str,
                vol.Optional(
                    CONF_UPDATE_INTERVAL,
                    default=current.get(CONF_UPDATE_INTERVAL, DEFAULT_UPDATE_INTERVAL),
                ): vol.All(vol.Coerce(int), vol.Range(min=1)),
                vol.Optional(
                    CONF_CONSIDER_NONE_OUTSIDE_HOURS,
                    default=current.get(
                        CONF_CONSIDER_NONE_OUTSIDE_HOURS,
                        DEFAULT_CONSIDER_NONE_OUTSIDE_HOURS,
                    ),
                ): bool,
            }
        )

        return self.async_show_form(step_id="init", data_schema=schema)
