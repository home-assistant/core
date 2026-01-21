"""Config flow to configure the USGS Earthquakes Feed integration."""

import logging
from typing import Any

import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import (
    CONF_LATITUDE,
    CONF_LONGITUDE,
    CONF_RADIUS,
    CONF_SCAN_INTERVAL,
)
from homeassistant.helpers import config_validation as cv

from .const import (
    CONF_FEED_TYPE,
    CONF_MINIMUM_MAGNITUDE,
    DEFAULT_MINIMUM_MAGNITUDE,
    DEFAULT_RADIUS,
    DEFAULT_SCAN_INTERVAL,
    DOMAIN,
    VALID_FEED_TYPES,
)

DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_FEED_TYPE): vol.In(VALID_FEED_TYPES),
        vol.Optional(CONF_RADIUS, default=DEFAULT_RADIUS): cv.positive_float,
        vol.Optional(
            CONF_MINIMUM_MAGNITUDE, default=DEFAULT_MINIMUM_MAGNITUDE
        ): cv.positive_float,
    }
)

_LOGGER = logging.getLogger(__name__)


class UsgsEarthquakesFeedFlowHandler(ConfigFlow, domain=DOMAIN):
    """Handle a USGS Earthquakes Feed config flow."""

    VERSION = 1
    MINOR_VERSION = 1

    async def _show_form(self, errors: dict[str, str] | None = None) -> ConfigFlowResult:
        """Show the form to the user."""
        return self.async_show_form(
            step_id="user", data_schema=DATA_SCHEMA, errors=errors or {}
        )

    async def async_step_import(
        self, import_data: dict[str, Any]
    ) -> ConfigFlowResult:
        """Import a config entry from configuration.yaml."""
        return await self.async_step_user(import_data)

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the start of the config flow."""
        _LOGGER.debug("User input: %s", user_input)
        if not user_input:
            return await self._show_form()

        latitude = user_input.get(CONF_LATITUDE, self.hass.config.latitude)
        user_input[CONF_LATITUDE] = latitude
        longitude = user_input.get(CONF_LONGITUDE, self.hass.config.longitude)
        user_input[CONF_LONGITUDE] = longitude

        # Create a unique ID based on location and feed type
        identifier = (
            f"{user_input[CONF_LATITUDE]}, {user_input[CONF_LONGITUDE]}, "
            f"{user_input[CONF_FEED_TYPE]}"
        )

        await self.async_set_unique_id(identifier)
        self._abort_if_unique_id_configured()

        scan_interval = user_input.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL)
        user_input[CONF_SCAN_INTERVAL] = scan_interval.total_seconds()

        minimum_magnitude = user_input.get(
            CONF_MINIMUM_MAGNITUDE, DEFAULT_MINIMUM_MAGNITUDE
        )
        user_input[CONF_MINIMUM_MAGNITUDE] = minimum_magnitude

        title = f"{user_input[CONF_FEED_TYPE]}"

        return self.async_create_entry(title=title, data=user_input)
