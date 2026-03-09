"""Config flow to configure the USGS Earthquakes Feed integration."""

from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol

from homeassistant.config_entries import (
    ConfigEntry,
    ConfigFlow,
    ConfigFlowResult,
    OptionsFlow,
)
from homeassistant.const import (
    CONF_LATITUDE,
    CONF_LONGITUDE,
    CONF_RADIUS,
    CONF_SCAN_INTERVAL,
)
from homeassistant.core import HomeAssistant, callback
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

_LOGGER = logging.getLogger(__name__)


def _get_data_schema(
    hass: HomeAssistant, user_input: dict[str, Any] | None = None
) -> vol.Schema:
    """Return the data schema for config flow."""
    if user_input is None:
        user_input = {}

    return vol.Schema(
        {
            vol.Optional(
                CONF_LATITUDE,
                default=user_input.get(CONF_LATITUDE, hass.config.latitude),
            ): cv.latitude,
            vol.Optional(
                CONF_LONGITUDE,
                default=user_input.get(CONF_LONGITUDE, hass.config.longitude),
            ): cv.longitude,
            vol.Required(
                CONF_FEED_TYPE,
                default=user_input.get(CONF_FEED_TYPE, "past_day_all_earthquakes"),
            ): vol.In(VALID_FEED_TYPES),
            vol.Optional(
                CONF_RADIUS,
                default=user_input.get(CONF_RADIUS, DEFAULT_RADIUS),
            ): cv.positive_float,
            vol.Optional(
                CONF_MINIMUM_MAGNITUDE,
                default=user_input.get(
                    CONF_MINIMUM_MAGNITUDE, DEFAULT_MINIMUM_MAGNITUDE
                ),
            ): cv.positive_float,
        }
    )


class UsgsEarthquakesFeedFlowHandler(ConfigFlow, domain=DOMAIN):
    """Handle a USGS Earthquakes Feed config flow."""

    VERSION = 1
    MINOR_VERSION = 1

    @staticmethod
    @callback
    def async_get_options_flow(
        config_entry: ConfigEntry,
    ) -> OptionsFlow:
        """Get the options flow for this handler."""
        return UsgsEarthquakesFeedOptionsFlowHandler(config_entry)

    async def _show_form(
        self,
        errors: dict[str, str] | None = None,
        user_input: dict[str, Any] | None = None,
    ) -> ConfigFlowResult:
        """Show the form to the user."""
        return self.async_show_form(
            step_id="user",
            data_schema=_get_data_schema(self.hass, user_input),
            errors=errors or {},
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

        # Create a unique ID based on location and feed type
        identifier = (
            f"{user_input[CONF_LATITUDE]}, {user_input[CONF_LONGITUDE]}, "
            f"{user_input[CONF_FEED_TYPE]}"
        )

        await self.async_set_unique_id(identifier)
        self._abort_if_unique_id_configured()

        scan_interval = user_input.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL)
        user_input[CONF_SCAN_INTERVAL] = scan_interval.total_seconds()

        title = user_input[CONF_FEED_TYPE]

        return self.async_create_entry(title=title, data=user_input)

    async def async_step_reconfigure(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle reconfiguration of the integration."""
        entry = self.hass.config_entries.async_get_entry(self.context["entry_id"])
        assert entry

        if user_input is not None:
            # Update scan interval
            scan_interval = user_input.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL)
            user_input[CONF_SCAN_INTERVAL] = scan_interval.total_seconds()

            # Update the unique ID if location or feed type changed
            new_identifier = (
                f"{user_input[CONF_LATITUDE]}, {user_input[CONF_LONGITUDE]}, "
                f"{user_input[CONF_FEED_TYPE]}"
            )

            # Only check for duplicate if the unique ID changed
            if new_identifier != entry.unique_id:
                await self.async_set_unique_id(new_identifier)
                self._abort_if_unique_id_configured()

            return self.async_update_reload_and_abort(
                entry,
                data=user_input,
                reason="reconfigure_successful",
            )

        return self.async_show_form(
            step_id="reconfigure",
            data_schema=_get_data_schema(self.hass, entry.data),
        )


class UsgsEarthquakesFeedOptionsFlowHandler(OptionsFlow):
    """Handle options flow for USGS Earthquakes Feed."""

    def __init__(self, config_entry: ConfigEntry) -> None:
        """Initialize options flow."""
        self.config_entry = config_entry

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Manage the options."""
        if user_input is not None:
            # Update scan interval
            scan_interval = user_input.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL)
            user_input[CONF_SCAN_INTERVAL] = scan_interval.total_seconds()

            # Store updated options; entry reload (if needed) is handled by options listener
            return self.async_create_entry(title="", data=user_input)
        return self.async_show_form(
            step_id="init",
            data_schema=_get_data_schema(self.hass, self.config_entry.data),
        )
