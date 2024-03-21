"""Config flow for Ollama conversation integration."""

from __future__ import annotations

import asyncio
import logging
import sys
from types import MappingProxyType
from typing import Any

import httpx
import ollama
import voluptuous as vol

from homeassistant.config_entries import (
    ConfigEntry,
    ConfigFlow,
    ConfigFlowResult,
    OptionsFlow,
)
from homeassistant.const import CONF_URL
from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.selector import (
    NumberSelector,
    NumberSelectorConfig,
    NumberSelectorMode,
    ObjectSelector,
    TemplateSelector,
    TextSelector,
    TextSelectorType,
)

from .const import (
    CONF_MAX_HISTORY,
    CONF_MODEL,
    CONF_MODEL_OPTIONS,
    CONF_PROMPT,
    DEFAULT_PROMPT,
    DEFAULT_TIMEOUT,
    DOMAIN,
    MAX_HISTORY_NO_LIMIT,
)

_LOGGER = logging.getLogger(__name__)

STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_URL): TextSelector({"type": TextSelectorType.URL}),
        vol.Required(CONF_MODEL): cv.string,
        vol.Required(
            CONF_PROMPT, description={"suggested_value": DEFAULT_PROMPT}
        ): TemplateSelector(),
        vol.Optional(CONF_MODEL_OPTIONS): ObjectSelector(),
        vol.Optional(
            CONF_MAX_HISTORY, description={"suggested_value": MAX_HISTORY_NO_LIMIT}
        ): NumberSelector(
            NumberSelectorConfig(
                min=0, max=sys.maxsize, step=1, mode=NumberSelectorMode.BOX
            )
        ),
    }
)


async def validate_input(hass: HomeAssistant, data: dict[str, Any]) -> None:
    """Validate the user input allows us to connect.

    Data has the keys from STEP_USER_DATA_SCHEMA with values provided by the user.
    """
    client = ollama.AsyncClient(host=data[CONF_URL])
    async with asyncio.timeout(DEFAULT_TIMEOUT):
        await client.list()


class OllamaConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Ollama conversation."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step."""
        if user_input is None:
            return self.async_show_form(
                step_id="user", data_schema=STEP_USER_DATA_SCHEMA
            )

        errors = {}

        try:
            await validate_input(self.hass, user_input)
        except (TimeoutError, httpx.ConnectError):
            errors["base"] = "cannot_connect"
        except Exception:  # pylint: disable=broad-except
            _LOGGER.exception("Unexpected exception")
            errors["base"] = "unknown"
        else:
            return self.async_create_entry(title="Ollama Conversation", data=user_input)

        return self.async_show_form(
            step_id="user", data_schema=STEP_USER_DATA_SCHEMA, errors=errors
        )

    @staticmethod
    def async_get_options_flow(
        config_entry: ConfigEntry,
    ) -> OptionsFlow:
        """Create the options flow."""
        return OllamaOptionsFlow(config_entry)


class OllamaOptionsFlow(OptionsFlow):
    """Ollama conversation options flow."""

    def __init__(self, config_entry: ConfigEntry) -> None:
        """Initialize options flow."""
        self.config_entry = config_entry

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Manage the options."""
        if user_input is not None:
            return self.async_create_entry(title="Ollama Conversation", data=user_input)

        options = self.config_entry.options or self.config_entry.data
        schema = ollama_config_option_schema(MappingProxyType(options))
        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema(schema),
        )


def ollama_config_option_schema(options: MappingProxyType[str, Any]) -> dict:
    """Ollama conversation options schema."""
    return {
        vol.Required(
            CONF_URL,
            description={"suggested_value": options[CONF_URL]},
        ): TextSelector({"type": TextSelectorType.URL}),
        vol.Required(
            CONF_MODEL,
            description={"suggested_value": options[CONF_MODEL]},
        ): cv.string,
        vol.Optional(
            CONF_MODEL_OPTIONS,
            description={"suggested_value": options.get(CONF_MODEL_OPTIONS)},
        ): ObjectSelector(),
        vol.Optional(
            CONF_PROMPT,
            description={"suggested_value": options[CONF_PROMPT]},
        ): TemplateSelector(),
        vol.Optional(
            CONF_MAX_HISTORY,
            description={
                "suggested_value": options.get(CONF_MAX_HISTORY, MAX_HISTORY_NO_LIMIT)
            },
        ): NumberSelector(
            NumberSelectorConfig(
                min=0, max=sys.maxsize, step=1, mode=NumberSelectorMode.BOX
            )
        ),
    }
