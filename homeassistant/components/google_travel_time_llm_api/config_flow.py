"""Config flow for Google Travel Time LLM API integration."""

from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_API_KEY
from homeassistant.core import HomeAssistant
import homeassistant.helpers.config_validation as cv

from .const import DOMAIN
from .helpers import InvalidApiKeyException, validate_config_entry

_LOGGER = logging.getLogger(__name__)


CONFIG_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_API_KEY): cv.string,
    }
)


class GoogleTravelTimeConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Google Maps Travel Time and LLM API."""

    VERSION = 1

    async def async_step_user(self, user_input=None) -> ConfigFlowResult:
        """Handle the initial step."""
        errors: dict[str, str] | None = None
        user_input = user_input or {}
        if user_input:
            errors = await validate_input(self.hass, user_input)
            if not errors:
                return self.async_create_entry(
                    title="Google Travel Time LLM API", data=user_input
                )

        return self.async_show_form(
            step_id="user",
            data_schema=self.add_suggested_values_to_schema(CONFIG_SCHEMA, user_input),
            errors=errors,
        )


async def validate_input(
    hass: HomeAssistant, user_input: dict[str, Any]
) -> dict[str, str] | None:
    """Validate the user input allows us to connect."""
    try:
        await hass.async_add_executor_job(
            validate_config_entry,
            hass,
            user_input[CONF_API_KEY],
        )
    except InvalidApiKeyException:
        return {"base": "invalid_auth"}

    return None
