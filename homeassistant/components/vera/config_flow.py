"""Config flow for Vera."""

from __future__ import annotations

from collections.abc import Mapping
import logging
import re
from typing import Any

import pyvera as pv
from requests.exceptions import RequestException
import voluptuous as vol

from homeassistant.config_entries import (
    SOURCE_IMPORT,
    SOURCE_USER,
    ConfigEntry,
    ConfigFlow,
    ConfigFlowResult,
    OptionsFlow,
)
from homeassistant.const import CONF_EXCLUDE, CONF_LIGHTS, CONF_SOURCE
from homeassistant.core import callback
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.typing import VolDictType

from .const import CONF_CONTROLLER, CONF_LEGACY_UNIQUE_ID, DOMAIN

LIST_REGEX = re.compile("[^0-9]+")
_LOGGER = logging.getLogger(__name__)


def fix_device_id_list(data: list[Any]) -> list[int]:
    """Fix the id list by converting it to a supported int list."""
    return str_to_int_list(list_to_str(data))


def str_to_int_list(data: str) -> list[int]:
    """Convert a string to an int list."""
    return [int(s) for s in LIST_REGEX.split(data) if len(s) > 0]


def list_to_str(data: list[Any]) -> str:
    """Convert an int list to a string."""
    return " ".join([str(i) for i in data])


def new_options(lights: list[int], exclude: list[int]) -> dict[str, list[int]]:
    """Create a standard options object."""
    return {CONF_LIGHTS: lights, CONF_EXCLUDE: exclude}


def options_schema(options: Mapping[str, Any] | None = None) -> VolDictType:
    """Return options schema."""
    options = options or {}
    return {
        vol.Optional(
            CONF_LIGHTS,
            default=list_to_str(options.get(CONF_LIGHTS, [])),
        ): str,
        vol.Optional(
            CONF_EXCLUDE,
            default=list_to_str(options.get(CONF_EXCLUDE, [])),
        ): str,
    }


def options_data(user_input: dict[str, str]) -> dict[str, list[int]]:
    """Return options dict."""
    return new_options(
        str_to_int_list(user_input.get(CONF_LIGHTS, "")),
        str_to_int_list(user_input.get(CONF_EXCLUDE, "")),
    )


class OptionsFlowHandler(OptionsFlow):
    """Options for the component."""

    def __init__(self, config_entry: ConfigEntry) -> None:
        """Init object."""
        self.config_entry = config_entry

    async def async_step_init(
        self,
        user_input: dict[str, str] | None = None,
    ) -> ConfigFlowResult:
        """Manage the options."""
        if user_input is not None:
            return self.async_create_entry(
                title="",
                data=options_data(user_input),
            )

        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema(options_schema(self.config_entry.options)),
        )


class VeraFlowHandler(ConfigFlow, domain=DOMAIN):
    """Vera config flow."""

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: ConfigEntry) -> OptionsFlowHandler:
        """Get the options flow."""
        return OptionsFlowHandler(config_entry)

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle user initiated flow."""
        if user_input is not None:
            return await self.async_step_finish(
                {
                    **user_input,
                    **options_data(user_input),
                    CONF_SOURCE: SOURCE_USER,
                    CONF_LEGACY_UNIQUE_ID: False,
                }
            )

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {vol.Required(CONF_CONTROLLER): str, **options_schema()}
            ),
        )

    async def async_step_import(self, import_data: dict[str, Any]) -> ConfigFlowResult:
        """Handle a flow initialized by import."""

        # If there are entities with the legacy unique_id, then this imported config
        # should also use the legacy unique_id for entity creation.
        entity_registry = er.async_get(self.hass)
        use_legacy_unique_id = (
            len(
                [
                    entry
                    for entry in entity_registry.entities.values()
                    if entry.platform == DOMAIN and entry.unique_id.isdigit()
                ]
            )
            > 0
        )

        return await self.async_step_finish(
            {
                **import_data,
                CONF_SOURCE: SOURCE_IMPORT,
                CONF_LEGACY_UNIQUE_ID: use_legacy_unique_id,
            }
        )

    async def async_step_finish(self, config: dict[str, Any]) -> ConfigFlowResult:
        """Validate and create config entry."""
        base_url = config[CONF_CONTROLLER] = config[CONF_CONTROLLER].rstrip("/")
        controller = pv.VeraController(base_url)

        # Verify the controller is online and get the serial number.
        try:
            await self.hass.async_add_executor_job(controller.refresh_data)
        except RequestException:
            _LOGGER.error("Failed to connect to vera controller %s", base_url)
            return self.async_abort(
                reason="cannot_connect", description_placeholders={"base_url": base_url}
            )

        await self.async_set_unique_id(controller.serial_number)
        self._abort_if_unique_id_configured(config)

        return self.async_create_entry(title=base_url, data=config)
