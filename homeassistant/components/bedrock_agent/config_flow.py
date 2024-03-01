"""Config flow for Amazon Bedrock Agent integration."""
from __future__ import annotations

import logging
from typing import Any

import boto3
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResult
from homeassistant.exceptions import HomeAssistantError

from .const import CONST_KEY_ID, CONST_KEY_SECRET, CONST_MODEL_ID, CONST_REGION, DOMAIN

_LOGGER = logging.getLogger(__name__)

STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONST_REGION): str,
        vol.Required(CONST_KEY_ID): str,
        vol.Required(CONST_KEY_SECRET): str,
        vol.Required(CONST_MODEL_ID): str,
    }
)


class PlaceholderHub:
    """Placeholder class to make tests pass."""

    def __init__(self, host: str) -> None:
        """Initialize."""
        self.host = host

    async def authenticate(self, username: str, password: str) -> bool:
        """Test if we can authenticate with the host."""
        return True


async def validate_input(hass: HomeAssistant, data: dict[str, Any]) -> dict[str, Any]:
    """Validate the user input allows us to connect."""

    bedrock = boto3.client(
        service_name="bedrock",
        region_name=data[CONST_REGION],
        aws_access_key_id=data[CONST_KEY_ID],
        aws_secret_access_key=data[CONST_KEY_SECRET],
    )

    response = None

    try:
        response = await hass.async_add_executor_job(bedrock.list_foundation_models)
    finally:
        bedrock.close()

    if response is None or response["ResponseMetadata"]["HTTPStatusCode"] != 200:
        raise CannotConnect

    return {"title": "Bedrock"}


class ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Amazon Bedrock Agent."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle the initial step."""
        errors: dict[str, str] = {}
        if user_input is not None:
            try:
                info = await validate_input(self.hass, user_input)
            except CannotConnect:
                errors["base"] = "cannot_connect"
            except InvalidAuth:
                errors["base"] = "invalid_auth"
            except Exception:  # pylint: disable=broad-except
                _LOGGER.exception("Unexpected exception")
                errors["base"] = "unknown"
            else:
                return self.async_create_entry(title=info["title"], data=user_input)

        return self.async_show_form(
            step_id="user", data_schema=STEP_USER_DATA_SCHEMA, errors=errors
        )


class CannotConnect(HomeAssistantError):
    """Error to indicate we cannot connect."""


class InvalidAuth(HomeAssistantError):
    """Error to indicate there is invalid auth."""
