"""Config flow for TickTickMod integration."""

import json
import logging
from typing import Any

import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_EMAIL, CONF_PASSWORD
from homeassistant.helpers.selector import (
    TextSelector,
    TextSelectorConfig,
    TextSelectorType,
)

from .const import CONF_ACCESS_TOKEN, CONF_CLIENT_ID, CONF_CLIENT_SECRET, DOMAIN

_LOGGER = logging.getLogger(__name__)

STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_CLIENT_ID): TextSelector(
            TextSelectorConfig(type=TextSelectorType.TEXT),
        ),
        vol.Required(CONF_CLIENT_SECRET): TextSelector(
            TextSelectorConfig(type=TextSelectorType.PASSWORD),
        ),
        vol.Required(CONF_EMAIL): TextSelector(
            TextSelectorConfig(type=TextSelectorType.EMAIL),
        ),
        vol.Required(CONF_PASSWORD): TextSelector(
            TextSelectorConfig(type=TextSelectorType.PASSWORD),
        ),
        vol.Optional(CONF_ACCESS_TOKEN): TextSelector(
            TextSelectorConfig(type=TextSelectorType.TEXT),
        ),
    }
)


class TickTickModConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for TickTickMod."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step."""
        errors: dict[str, str] = {}
        if user_input is not None:
            try:
                _LOGGER.debug("Received user input: %s", user_input)
                # Validate the JSON format of the access token if provided
                if user_input.get(CONF_ACCESS_TOKEN):
                    access_token = json.loads(user_input[CONF_ACCESS_TOKEN])
                    _LOGGER.debug(
                        "Access token JSON parsed successfully: %s", access_token
                    )

                # For now, simply return a successful result without performing any authentication
                await self.async_set_unique_id("ticktick_mod")
                self._abort_if_unique_id_configured()
                return self.async_create_entry(
                    title=user_input[CONF_EMAIL], data=user_input
                )
            except json.JSONDecodeError as e:
                _LOGGER.exception("Invalid JSON format: %s", e)
                errors["base"] = "invalid_json"
            except Exception as e:
                _LOGGER.exception("Unexpected exception: %s", e)
                errors["base"] = "unknown"

        return self.async_show_form(
            step_id="user", data_schema=STEP_USER_DATA_SCHEMA, errors=errors
        )
