"""Config flow for Logitech Harmony Hub integration."""

from __future__ import annotations

import asyncio
import logging
from typing import Any
from urllib.parse import urlparse

from aioharmony.hubconnector_websocket import HubConnector
import aiohttp
import voluptuous as vol

from homeassistant.components import ssdp
from homeassistant.components.remote import (
    ATTR_ACTIVITY,
    ATTR_DELAY_SECS,
    DEFAULT_DELAY_SECS,
)
from homeassistant.config_entries import (
    ConfigEntry,
    ConfigFlow,
    ConfigFlowResult,
    OptionsFlow,
)
from homeassistant.const import CONF_HOST, CONF_NAME
from homeassistant.core import callback
from homeassistant.exceptions import HomeAssistantError

from .const import DOMAIN, PREVIOUS_ACTIVE_ACTIVITY, UNIQUE_ID
from .data import HarmonyConfigEntry
from .util import (
    find_best_name_for_remote,
    find_unique_id_for_remote,
    get_harmony_client_if_available,
)

_LOGGER = logging.getLogger(__name__)

DATA_SCHEMA = vol.Schema(
    {vol.Required(CONF_HOST): str, vol.Required(CONF_NAME): str}, extra=vol.ALLOW_EXTRA
)


async def validate_input(data: dict[str, Any]) -> dict[str, Any]:
    """Validate the user input allows us to connect.

    Data has the keys from DATA_SCHEMA with values provided by the user.
    """
    harmony = await get_harmony_client_if_available(data[CONF_HOST])
    if not harmony:
        raise CannotConnect

    return {
        CONF_NAME: find_best_name_for_remote(data, harmony),
        CONF_HOST: data[CONF_HOST],
        UNIQUE_ID: find_unique_id_for_remote(harmony),
    }


class HarmonyConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Logitech Harmony Hub."""

    VERSION = 1

    def __init__(self) -> None:
        """Initialize the Harmony config flow."""
        self.harmony_config: dict[str, Any] = {}

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step."""
        errors: dict[str, str] = {}
        if user_input is not None:
            try:
                validated = await validate_input(user_input)
            except CannotConnect:
                errors["base"] = "cannot_connect"
            except Exception:
                _LOGGER.exception("Unexpected exception")
                errors["base"] = "unknown"

            if "base" not in errors:
                await self.async_set_unique_id(validated[UNIQUE_ID])
                self._abort_if_unique_id_configured()
                return await self._async_create_entry_from_valid_input(
                    validated, user_input
                )

        # Return form
        return self.async_show_form(
            step_id="user", data_schema=DATA_SCHEMA, errors=errors
        )

    async def async_step_ssdp(
        self, discovery_info: ssdp.SsdpServiceInfo
    ) -> ConfigFlowResult:
        """Handle a discovered Harmony device."""
        _LOGGER.debug("SSDP discovery_info: %s", discovery_info)

        parsed_url = urlparse(discovery_info.ssdp_location)
        friendly_name = discovery_info.upnp[ssdp.ATTR_UPNP_FRIENDLY_NAME]

        self._async_abort_entries_match({CONF_HOST: parsed_url.hostname})

        self.context["title_placeholders"] = {"name": friendly_name}

        self.harmony_config = {
            CONF_HOST: parsed_url.hostname,
            CONF_NAME: friendly_name,
        }

        connector = HubConnector(parsed_url.hostname, asyncio.Queue())
        try:
            remote_id = await connector.get_remote_id()
        except aiohttp.ClientError:
            return self.async_abort(reason="cannot_connect")
        finally:
            await connector.async_close_session()

        unique_id = str(remote_id)
        await self.async_set_unique_id(str(unique_id))
        self._abort_if_unique_id_configured(
            updates={CONF_HOST: self.harmony_config[CONF_HOST]}
        )
        self.harmony_config[UNIQUE_ID] = unique_id
        return await self.async_step_link()

    async def async_step_link(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Attempt to link with the Harmony."""
        errors: dict[str, str] = {}

        if user_input is not None:
            # Everything was validated in async_step_ssdp
            # all we do now is create.
            return await self._async_create_entry_from_valid_input(
                self.harmony_config, {}
            )

        self._set_confirm_only()
        return self.async_show_form(
            step_id="link",
            errors=errors,
            description_placeholders={
                CONF_HOST: self.harmony_config[CONF_NAME],
                CONF_NAME: self.harmony_config[CONF_HOST],
            },
        )

    @staticmethod
    @callback
    def async_get_options_flow(
        config_entry: ConfigEntry,
    ) -> OptionsFlowHandler:
        """Get the options flow for this handler."""
        return OptionsFlowHandler(config_entry)

    async def _async_create_entry_from_valid_input(
        self, validated: dict[str, Any], user_input: dict[str, Any]
    ) -> ConfigFlowResult:
        """Single path to create the config entry from validated input."""

        data = {
            CONF_NAME: validated[CONF_NAME],
            CONF_HOST: validated[CONF_HOST],
        }
        # Options from yaml are preserved, we will pull them out when
        # we setup the config entry
        data.update(_options_from_user_input(user_input))

        return self.async_create_entry(title=validated[CONF_NAME], data=data)


def _options_from_user_input(user_input: dict[str, Any]) -> dict[str, Any]:
    options: dict[str, Any] = {}
    if ATTR_ACTIVITY in user_input:
        options[ATTR_ACTIVITY] = user_input[ATTR_ACTIVITY]
    if ATTR_DELAY_SECS in user_input:
        options[ATTR_DELAY_SECS] = user_input[ATTR_DELAY_SECS]
    return options


class OptionsFlowHandler(OptionsFlow):
    """Handle a option flow for Harmony."""

    def __init__(self, config_entry: HarmonyConfigEntry) -> None:
        """Initialize options flow."""
        self.config_entry = config_entry

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle options flow."""
        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)

        remote = self.config_entry.runtime_data
        data_schema = vol.Schema(
            {
                vol.Optional(
                    ATTR_DELAY_SECS,
                    default=self.config_entry.options.get(
                        ATTR_DELAY_SECS, DEFAULT_DELAY_SECS
                    ),
                ): vol.Coerce(float),
                vol.Optional(
                    ATTR_ACTIVITY,
                    default=self.config_entry.options.get(
                        ATTR_ACTIVITY, PREVIOUS_ACTIVE_ACTIVITY
                    ),
                ): vol.In([PREVIOUS_ACTIVE_ACTIVITY, *remote.activity_names]),
            }
        )
        return self.async_show_form(step_id="init", data_schema=data_schema)


class CannotConnect(HomeAssistantError):
    """Error to indicate we cannot connect."""
