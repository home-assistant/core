"""Config flow to configure IPMA component."""

import logging
from typing import Any, override

import probatio
from pyipma import IPMAException
from pyipma.api import IPMA_API
from pyipma.location import Location

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_LATITUDE, CONF_LOCATION, CONF_LONGITUDE
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.selector import LocationSelector, LocationSelectorConfig

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)


class IpmaFlowHandler(ConfigFlow, domain=DOMAIN):
    """Config flow for IPMA component."""

    VERSION = 1

    @override
    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle a flow initialized by the user."""
        errors = {}

        if user_input is not None:
            self._async_abort_entries_match(user_input[CONF_LOCATION])

            api = IPMA_API(async_get_clientsession(self.hass))

            try:
                location = await Location.get(
                    api,
                    user_input[CONF_LOCATION][CONF_LATITUDE],
                    user_input[CONF_LOCATION][CONF_LONGITUDE],
                )
            except IPMAException:
                _LOGGER.exception("Unexpected exception")
                errors["base"] = "unknown"
            else:
                return self.async_create_entry(
                    title=location.name, data=user_input[CONF_LOCATION]
                )

        return self.async_show_form(
            step_id="user",
            data_schema=self.add_suggested_values_to_schema(
                probatio.Schema(
                    {
                        probatio.Required(CONF_LOCATION): LocationSelector(
                            LocationSelectorConfig(radius=False)
                        ),
                    }
                ),
                {
                    CONF_LOCATION: {
                        CONF_LATITUDE: self.hass.config.latitude,
                        CONF_LONGITUDE: self.hass.config.longitude,
                    }
                },
            ),
            errors=errors,
        )
