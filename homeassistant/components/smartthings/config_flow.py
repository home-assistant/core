"""Config flow to configure SmartThings."""

import logging
from typing import Any

import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_ACCESS_TOKEN

from .const import CONF_LOCATION_ID, DOMAIN

_LOGGER = logging.getLogger(__name__)


class SmartThingsConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle configuration of SmartThings integrations."""

    VERSION = 3

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle a flow start."""
        if not user_input:
            return self.async_show_form(
                step_id="user",
                data_schema=vol.Schema(
                    {
                        vol.Required(CONF_ACCESS_TOKEN): str,
                        vol.Required(CONF_LOCATION_ID): str,
                    }
                ),
            )
        return self.async_create_entry(
            title="SmartThings",
            data=user_input,
        )
