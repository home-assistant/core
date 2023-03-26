"""Config flow for OpenAI Conversation integration."""
from __future__ import annotations

from functools import partial
import logging
import types
from types import MappingProxyType
from typing import Any

import openai
from openai import error
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import CONF_API_KEY
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers.selector import (
    NumberSelector,
    NumberSelectorConfig,
    TemplateSelector,
)

from .const import (
    CONF_MAX_TOKENS,
    CONF_MODEL,
    CONF_PROMPT,
    CONF_TEMPERATURE,
    CONF_TOP_P,
    DEFAULT_MAX_TOKENS,
    DEFAULT_MODEL,
    DEFAULT_PROMPT,
    DEFAULT_TEMPERATURE,
    DEFAULT_TOP_P,
    DOMAIN,
)

_LOGGER = logging.getLogger(__name__)

STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_API_KEY): str,
    }
)

DEFAULT_OPTIONS = types.MappingProxyType(
    {
        CONF_PROMPT: DEFAULT_PROMPT,
        CONF_MODEL: DEFAULT_MODEL,
        CONF_MAX_TOKENS: DEFAULT_MAX_TOKENS,
        CONF_TOP_P: DEFAULT_TOP_P,
        CONF_TEMPERATURE: DEFAULT_TEMPERATURE,
    }
)


async def validate_input(hass: HomeAssistant, data: dict[str, Any]) -> None:
    """Validate the user input allows us to connect.

    Data has the keys from STEP_USER_DATA_SCHEMA with values provided by the user.
    """
    openai.api_key = data[CONF_API_KEY]
    await hass.async_add_executor_job(partial(openai.Engine.list, request_timeout=10))


class ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for OpenAI Conversation."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle the initial step."""
        if self._async_current_entries():
            return self.async_abort(reason="single_instance_allowed")

        if user_input is None:
            return self.async_show_form(
                step_id="user", data_schema=STEP_USER_DATA_SCHEMA
            )

        errors = {}

        try:
            await validate_input(self.hass, user_input)
        except error.APIConnectionError:
            errors["base"] = "cannot_connect"
        except error.AuthenticationError:
            errors["base"] = "invalid_auth"
        except Exception:  # pylint: disable=broad-except
            _LOGGER.exception("Unexpected exception")
            errors["base"] = "unknown"
        else:
            return self.async_create_entry(title="OpenAI Conversation", data=user_input)

        return self.async_show_form(
            step_id="user", data_schema=STEP_USER_DATA_SCHEMA, errors=errors
        )

    @staticmethod
    def async_get_options_flow(
        config_entry: config_entries.ConfigEntry,
    ) -> config_entries.OptionsFlow:
        """Create the options flow."""
        return OptionsFlow(config_entry)


class OptionsFlow(config_entries.OptionsFlow):
    """OpenAI config flow options handler."""

    def __init__(self, config_entry: config_entries.ConfigEntry) -> None:
        """Initialize options flow."""
        self.config_entry = config_entry

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Manage the options."""
        if user_input is not None:
            return self.async_create_entry(title="OpenAI Conversation", data=user_input)
        schema = openai_config_option_schema(self.config_entry.options)
        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema(schema),
        )


def openai_config_option_schema(options: MappingProxyType[str, Any]) -> dict:
    """Return a schema for OpenAI completion options."""
    if not options:
        options = DEFAULT_OPTIONS
    return {
        vol.Required(CONF_PROMPT, default=options.get(CONF_PROMPT)): TemplateSelector(),
        vol.Required(CONF_MODEL, default=options.get(CONF_MODEL)): str,
        vol.Required(CONF_MAX_TOKENS, default=options.get(CONF_MAX_TOKENS)): int,
        vol.Required(CONF_TOP_P, default=options.get(CONF_TOP_P)): NumberSelector(
            NumberSelectorConfig(min=0, max=1, step=0.05)
        ),
        vol.Required(
            CONF_TEMPERATURE, default=options.get(CONF_TEMPERATURE)
        ): NumberSelector(NumberSelectorConfig(min=0, max=1, step=0.05)),
    }
