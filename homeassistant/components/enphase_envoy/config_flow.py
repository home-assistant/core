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
from homeassistant.exceptions import HomeAssistantError

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

ENVOY = "Envoy"

CONF_SERIAL = "serial"


async def validate_input(hass: HomeAssistant, data: dict[str, Any]) -> dict[str, Any]:
    """Validate the user input allows us to connect.

    Data has the keys from STEP_USER_DATA_SCHEMA with values provided by the user.
    """
    envoy_reader = EnvoyReader(
        data[CONF_HOST], data[CONF_USERNAME], data[CONF_PASSWORD], inverters=True
    )

    try:
        await envoy_reader.getData()
    except httpx.HTTPStatusError as err:
        raise InvalidAuth from err
    except (AttributeError, httpx.HTTPError) as err:
        raise CannotConnect from err


class ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Enphase Envoy."""

    VERSION = 1
    CONNECTION_CLASS = config_entries.CONN_CLASS_LOCAL_POLL

    def __init__(self):
        """Initialize an envoy flow."""
        self.ip_address = None
        self.username = None
        self.serial = None

    @callback
    def _async_generate_schema(self, include_ip_address=True):
        """Generate schema."""
        schema = {}

        if include_ip_address:
            schema[vol.Required(CONF_HOST, default=self.ip_address)] = str

        schema.update(
            {
                vol.Optional(CONF_USERNAME, default=self.username or "envoy"): str,
                vol.Optional(CONF_PASSWORD, default=""): str,
            }
        )
        return vol.Schema(schema)

    async def async_step_import(self, import_config):
        """Handle a flow import."""
        host = import_config[CONF_IP_ADDRESS]
        if host in self._async_current_hosts():
            return self.async_abort(reason="already_configured")

        self.ip_address = host
        self.username = import_config[CONF_USERNAME]
        return await self.async_step_user(
            {
                CONF_HOST: host,
                CONF_NAME: import_config[CONF_NAME],
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
        self.context["title_placeholders"] = {CONF_SERIAL: self.serial}
        return await self.async_step_user()

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        """Handle the initial step."""
        errors = {}

        if user_input is not None:
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
                if CONF_NAME in user_input:
                    name = user_input[CONF_NAME]
                else:
                    name = f"{ENVOY} {self.serial}" if self.serial else ENVOY
                return self.async_create_entry(
                    title=name, data={CONF_NAME: name, **user_input}
                )

        return self.async_show_form(
            step_id="user",
            data_schema=self._async_generate_schema(
                include_ip_address=not self.ip_address
            ),
            errors=errors,
        )


class CannotConnect(HomeAssistantError):
    """Error to indicate we cannot connect."""


class InvalidAuth(HomeAssistantError):
    """Error to indicate there is invalid auth."""
