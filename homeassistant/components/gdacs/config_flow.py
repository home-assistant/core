"""Config flow to configure the GDACS integration."""

import logging
from typing import Any, override

import probatio

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import (
    CONF_LATITUDE,
    CONF_LOCATION,
    CONF_LONGITUDE,
    CONF_RADIUS,
)
from homeassistant.helpers.selector import LocationSelector, LocationSelectorConfig

from .const import DEFAULT_RADIUS, DOMAIN

DATA_SCHEMA = probatio.Schema(
    {
        probatio.Required(CONF_LOCATION): LocationSelector(
            LocationSelectorConfig(radius=True)
        ),
    }
)

_LOGGER = logging.getLogger(__name__)


class GdacsFlowHandler(ConfigFlow, domain=DOMAIN):
    """Handle a GDACS config flow."""

    VERSION = 2

    async def _show_form(
        self, errors: dict[str, str] | None = None
    ) -> ConfigFlowResult:
        """Show the form to the user."""
        return self.async_show_form(
            step_id="user",
            data_schema=self.add_suggested_values_to_schema(
                DATA_SCHEMA,
                {
                    CONF_LOCATION: {
                        CONF_LATITUDE: self.hass.config.latitude,
                        CONF_LONGITUDE: self.hass.config.longitude,
                        CONF_RADIUS: DEFAULT_RADIUS,
                    }
                },
            ),
            errors=errors or {},
        )

    @override
    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the start of the config flow."""
        _LOGGER.debug("User input: %s", user_input)
        if not user_input:
            return await self._show_form()

        await self.async_set_unique_id(
            f"{user_input[CONF_LOCATION][CONF_LATITUDE]}, "
            f"{user_input[CONF_LOCATION][CONF_LONGITUDE]}"
        )
        self._abort_if_unique_id_configured()
        user_input.setdefault(CONF_LOCATION, DEFAULT_RADIUS)
        return self.async_create_entry(
            title="Global Disaster Alert and Coordination System", data=user_input
        )
