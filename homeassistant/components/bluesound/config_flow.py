"""Config flow for bluesound."""

import logging
from typing import Any

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.config_entries import ConfigFlowResult
from homeassistant.const import CONF_HOST, CONF_NAME, CONF_PORT

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)


class BluesoundConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Bluesound config flow."""

    VERSION = 1
    MINOR_VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle a flow initiated by the user."""
        if user_input is not None:
            return self.async_create_entry(
                title=user_input[CONF_NAME],
                data=user_input,
            )

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_NAME, default="Bluesound"): str,
                    vol.Required(CONF_HOST, description="host"): str,
                    vol.Optional(CONF_PORT, default=11000): int,
                }
            ),
        )
