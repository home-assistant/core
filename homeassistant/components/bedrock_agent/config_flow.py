"""Config flow for Amazon Bedrock Agent integration."""
from __future__ import annotations

import logging
from typing import Any

import boto3
import voluptuous as vol

from homeassistant.config_entries import (
    ConfigEntry,
    ConfigFlow,
    ConfigFlowResult,
    OptionsFlow,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError

from .const import CONST_KEY_ID, CONST_KEY_SECRET, CONST_MODEL_ID, CONST_REGION, DOMAIN

LOGGER = logging.getLogger(__name__)

STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONST_REGION): str,
        vol.Required(CONST_KEY_ID): str,
        vol.Required(CONST_KEY_SECRET): str,
        vol.Required(CONST_MODEL_ID): str,
    }
)

STEP_INIT_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONST_REGION): str,
        vol.Required(CONST_MODEL_ID): str,
    }
)


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
    except Exception as err:  # pylint: disable=broad-except
        LOGGER.exception("Unexpected exception")
        raise CannotConnect from err
    finally:
        bedrock.close()

    if response is None or response["ResponseMetadata"]["HTTPStatusCode"] != 200:
        raise CannotConnect

    return {"title": "Bedrock"}


class BedrockAgentConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Amazon Bedrock Agent."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
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
                LOGGER.exception("Unexpected exception")
                errors["base"] = "unknown"
            else:
                return self.async_create_entry(title=info["title"], data=user_input)

        return self.async_show_form(
            step_id="user", data_schema=STEP_USER_DATA_SCHEMA, errors=errors
        )

    @staticmethod
    @callback
    def async_get_options_flow(
        config_entry: ConfigEntry,
    ) -> OptionsFlow:
        """Create the options flow."""
        return OptionsFlowHandler(config_entry)


class CannotConnect(HomeAssistantError):
    """Error to indicate we cannot connect."""


class InvalidAuth(HomeAssistantError):
    """Error to indicate there is invalid auth."""


class OptionsFlowHandler(OptionsFlow):
    """Handle a options flow for Amazon Bedrock Agent."""

    def __init__(self, config_entry: ConfigEntry) -> None:
        """Initialize options flow."""
        self.config_entry = config_entry

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Manage the options."""
        errors: dict[str, str] = {}
        if user_input is not None:
            try:
                info = await validate_input(self.hass, user_input)
                self.hass.config_entries.async_update_entry(
                    self.config_entry, data=user_input
                )
            except CannotConnect:
                errors["base"] = "cannot_connect"
            except InvalidAuth:
                errors["base"] = "invalid_auth"
            except Exception:  # pylint: disable=broad-except
                LOGGER.exception("Unexpected exception")
                errors["base"] = "unknown"
            else:
                return self.async_create_entry(title=info["title"], data=user_input)

        options_schema = vol.Schema(
            {
                vol.Required(
                    CONST_REGION, default=self.config_entry.data[CONST_REGION]
                ): str,
                vol.Required(
                    CONST_KEY_ID, default=self.config_entry.data[CONST_KEY_ID]
                ): str,
                vol.Required(
                    CONST_KEY_SECRET, default=self.config_entry.data[CONST_KEY_SECRET]
                ): str,
                vol.Required(
                    CONST_MODEL_ID, default=self.config_entry.data[CONST_MODEL_ID]
                ): str,
            }
        )

        return self.async_show_form(
            step_id="init", data_schema=options_schema, errors=errors
        )
