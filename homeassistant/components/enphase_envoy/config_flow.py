"""Config flow for Enphase Envoy integration."""
from __future__ import annotations

import logging
from typing import Any

from envoy_reader.envoy_reader import EnvoyReader
import httpx
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import (
    CONF_HOST,
    CONF_IP_ADDRESS,
    CONF_NAME,
    CONF_PASSWORD,
    CONF_USERNAME,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.data_entry_flow import FlowResult
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.httpx_client import get_async_client

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

ENVOY = "Envoy"

CONF_SERIAL = "serial"


async def validate_input(hass: HomeAssistant, data: dict[str, Any]) -> dict[str, Any]:
    """Validate the user input allows us to connect."""
    envoy_reader = EnvoyReader(
        data[CONF_HOST],
        data[CONF_USERNAME],
        data[CONF_PASSWORD],
        inverters=False,
        async_client=get_async_client(hass),
    )

    try:
        await envoy_reader.getData()
    except httpx.HTTPStatusError as err:
        raise InvalidAuth from err
    except (RuntimeError, httpx.HTTPError) as err:
        raise CannotConnect from err


class ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Enphase Envoy."""

    VERSION = 1
    CONNECTION_CLASS = config_entries.CONN_CLASS_LOCAL_POLL

    def __init__(self):
        """Initialize an envoy flow."""
        self.ip_address = None
        self.name = None
        self.username = None
        self.serial = None
        self._reauth_entry = None

    @callback
    def _async_generate_schema(self):
        """Generate schema."""
        schema = {}

        if self.ip_address:
            schema[vol.Required(CONF_HOST, default=self.ip_address)] = vol.In(
                [self.ip_address]
            )
        else:
            schema[vol.Required(CONF_HOST)] = str

        schema[vol.Optional(CONF_USERNAME, default=self.username or "envoy")] = str
        schema[vol.Optional(CONF_PASSWORD, default="")] = str
        return vol.Schema(schema)

    async def async_step_import(self, import_config):
        """Handle a flow import."""
        self.ip_address = import_config[CONF_IP_ADDRESS]
        self.username = import_config[CONF_USERNAME]
        self.name = import_config[CONF_NAME]
        return await self.async_step_user(
            {
                CONF_HOST: import_config[CONF_IP_ADDRESS],
                CONF_USERNAME: import_config[CONF_USERNAME],
                CONF_PASSWORD: import_config[CONF_PASSWORD],
            }
        )

    @callback
    def _async_current_hosts(self):
        """Return a set of hosts."""
        return {
            entry.data[CONF_HOST]
            for entry in self._async_current_entries(include_ignore=False)
            if CONF_HOST in entry.data
        }

    async def async_step_zeroconf(self, discovery_info):
        """Handle a flow initialized by zeroconf discovery."""
        self.serial = discovery_info["properties"]["serialnum"]
        await self.async_set_unique_id(self.serial)
        self.ip_address = discovery_info[CONF_HOST]
        self._abort_if_unique_id_configured({CONF_HOST: self.ip_address})
        for entry in self._async_current_entries(include_ignore=False):
            if (
                entry.unique_id is None
                and CONF_HOST in entry.data
                and entry.data[CONF_HOST] == self.ip_address
            ):
                title = f"{ENVOY} {self.serial}" if entry.title == ENVOY else ENVOY
                self.hass.config_entries.async_update_entry(
                    entry, title=title, unique_id=self.serial
                )
                self.hass.async_create_task(
                    self.hass.config_entries.async_reload(entry.entry_id)
                )
                return self.async_abort(reason="already_configured")

        return await self.async_step_user()

    async def async_step_reauth(self, user_input):
        """Handle configuration by re-auth."""
        self._reauth_entry = self.hass.config_entries.async_get_entry(
            self.context["entry_id"]
        )
        return await self.async_step_user()

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle the initial step."""
        errors = {}

        if user_input is not None:
            if (
                not self._reauth_entry
                and user_input[CONF_HOST] in self._async_current_hosts()
            ):
                return self.async_abort(reason="already_configured")
            try:
                await validate_input(self.hass, user_input)
            except CannotConnect:
                errors["base"] = "cannot_connect"
            except InvalidAuth:
                errors["base"] = "invalid_auth"
            except Exception:  # pylint: disable=broad-except
                _LOGGER.exception("Unexpected exception")
                errors["base"] = "unknown"
            else:
                data = user_input.copy()
                if self.serial:
                    data[CONF_NAME] = f"{ENVOY} {self.serial}"
                else:
                    data[CONF_NAME] = self.name or ENVOY
                if self._reauth_entry:
                    self.hass.config_entries.async_update_entry(
                        self._reauth_entry,
                        data=data,
                    )
                    return self.async_abort(reason="reauth_successful")
                return self.async_create_entry(title=data[CONF_NAME], data=data)

        if self.serial:
            self.context["title_placeholders"] = {
                CONF_SERIAL: self.serial,
                CONF_HOST: self.ip_address,
            }
        return self.async_show_form(
            step_id="user",
            data_schema=self._async_generate_schema(),
            errors=errors,
        )


class CannotConnect(HomeAssistantError):
    """Error to indicate we cannot connect."""


class InvalidAuth(HomeAssistantError):
    """Error to indicate there is invalid auth."""
