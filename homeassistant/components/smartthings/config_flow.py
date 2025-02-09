"""Config flow to configure SmartThings."""

import logging
from typing import Any

from pysmartthings import SmartThings
import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_ACCESS_TOKEN
from homeassistant.helpers.selector import (
    SelectOptionDict,
    SelectSelector,
    SelectSelectorConfig,
)

from .const import CONF_LOCATION_ID, DOMAIN

_LOGGER = logging.getLogger(__name__)


class SmartThingsConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle configuration of SmartThings integrations."""

    VERSION = 3

    _token: str

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle a flow start."""
        if user_input:
            self._token = user_input[CONF_ACCESS_TOKEN]
            return await self.async_step_location()
        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_ACCESS_TOKEN): str,
                }
            ),
        )

    async def async_step_location(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle a flow start."""
        if user_input:
            return self.async_create_entry(
                title="SmartThings",
                data={
                    CONF_ACCESS_TOKEN: self._token,
                    **user_input,
                },
            )
        client = SmartThings(self._token)
        locations = await client.get_locations()
        if not locations:
            return self.async_abort(reason="no_locations")
        if len(locations) == 1:
            return await self.async_step_location(
                {CONF_LOCATION_ID: locations[0].location_id}
            )
        options = [
            SelectOptionDict(value=location.location_id, label=location.name)
            for location in locations
        ]
        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_LOCATION_ID): SelectSelector(
                        SelectSelectorConfig(options=options)
                    ),
                }
            ),
        )
