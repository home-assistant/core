"""Config flow for moonraker integration."""
from __future__ import annotations

import asyncio
import logging
from typing import Any

from aiohttp import ClientSession
from moonraker_api import ClientNotAuthenticatedError, MoonrakerClient
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.components import zeroconf
from homeassistant.const import CONF_API_KEY, CONF_HOST, CONF_NAME, CONF_PORT, CONF_SSL
from homeassistant.core import HomeAssistant, callback
from homeassistant.data_entry_flow import FlowResult
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.aiohttp_client import async_get_clientsession
import homeassistant.helpers.config_validation as cv

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)


def _schema_with_defaults(host="", port=7125, ssl=False, api_key=""):
    return vol.Schema(
        {
            vol.Required(CONF_HOST, default=host): str,
            vol.Required(CONF_PORT, default=port): cv.port,
            vol.Required(CONF_SSL, default=ssl): bool,
            vol.Optional(CONF_API_KEY, default=api_key): str,
        },
        extra=vol.ALLOW_EXTRA,
    )


class MoonrakerHub:
    """API shim to validate configuration."""

    def __init__(self, host: str, port: int, ssl: bool, session: ClientSession) -> None:
        """Initialize."""
        self.host: str = host
        self.port: int = port
        self.ssl: bool = ssl
        self.session: ClientSession = session
        self.printer_info: dict[str, Any] = {}
        self.system_info: dict[str, Any] = {}

    async def authenticate(self, api_key: str) -> bool:
        """Test if we can authenticate with the host."""
        client = MoonrakerClient(
            host=self.host,
            port=self.port,
            ssl=self.ssl,
            api_key=api_key,
            session=self.session,
            listener=None,
        )
        connected = await client.connect()
        self.printer_info = await client.call_method("printer.info")
        self.system_info = await client.call_method("machine.system_info")
        await client.disconnect()
        return connected


async def validate_input(hass: HomeAssistant, data: dict[str, Any]) -> dict[str, Any]:
    """Validate the user input allows us to connect.

    Data has the keys from STEP_USER_DATA_SCHEMA with values provided by the user.
    """
    clientsession = async_get_clientsession(hass)
    hub = MoonrakerHub(data[CONF_HOST], data[CONF_PORT], data[CONF_SSL], clientsession)

    try:
        if not await hub.authenticate(data[CONF_API_KEY]):
            raise CannotConnect
    except ClientNotAuthenticatedError as error:
        raise InvalidAuth from error
    except asyncio.TimeoutError as error:
        raise CannotConnect from error

    # Return info that you want to store in the config entry.
    uuid = None
    try:
        uuid = hub.system_info["system_info"]["cpu_info"]["serial_number"]
    except KeyError:
        pass
    return {"title": hub.printer_info.get("hostname"), "unique_id": uuid}


class ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for moonraker."""

    VERSION = 1
    api_key_task = None

    def __init__(self) -> None:
        """Handle a config flow for OctoPrint."""
        self.discovery_schema = None
        self._reauth_entry: config_entries.ConfigEntry | None = None

    @callback
    def _async_current_hosts(self):
        """Return a set of hosts."""
        return {
            entry.data[CONF_HOST]
            for entry in self._async_current_entries()
            if CONF_HOST in entry.data
        }

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle the initial step."""
        if user_input is None:
            data = self.discovery_schema or _schema_with_defaults()
            return self.async_show_form(step_id="user", data_schema=data)

        if user_input[CONF_HOST]:
            if (
                not self._reauth_entry
                and user_input[CONF_HOST] in self._async_current_hosts()
            ):
                return self.async_abort(reason="already_configured")

            errors = {}
            try:
                info = await validate_input(self.hass, user_input)
            except CannotConnect:
                errors["base"] = "cannot_connect"
            except InvalidAuth:
                errors["base"] = "invalid_api_key"
            except Exception:  # pylint: disable=broad-except
                _LOGGER.exception("Unexpected exception")
                errors["base"] = "unknown"
            else:
                if self._reauth_entry:
                    self.hass.config_entries.async_update_entry(
                        self._reauth_entry,
                        data=user_input,
                    )
                    return self.async_abort(reason="reauth_successful")
                await self.async_set_unique_id(info.get("unique_id"))
                self._abort_if_unique_id_configured()
                return self.async_create_entry(title=info["title"], data=user_input)

        return self.async_show_form(
            step_id="user",
            data_schema=_schema_with_defaults(
                user_input[CONF_HOST],
                user_input[CONF_PORT],
                user_input[CONF_SSL],
                user_input[CONF_API_KEY],
            ),
            errors=errors,
        )

    async def async_step_zeroconf(
        self, discovery_info: zeroconf.ZeroconfServiceInfo
    ) -> FlowResult:
        """Handle discovery flow."""
        local_name = discovery_info.hostname[:-1]
        node_name = local_name[: -len(".local")]
        address = discovery_info.properties.get("address", discovery_info.host)

        await self.async_set_unique_id(node_name)
        self._abort_if_unique_id_configured(updates={CONF_HOST: discovery_info.host})

        if local_name in self._async_current_hosts():
            return self.async_abort(reason="already_configured")
        if address in self._async_current_hosts():
            return self.async_abort(reason="already_configured")

        node_type = f".{discovery_info.type}"
        self.context["title_placeholders"] = {
            CONF_HOST: local_name,
            CONF_NAME: discovery_info.name[: -len(node_type)],
        }

        self.discovery_schema = _schema_with_defaults(
            host=local_name, port=discovery_info.port
        )

        return await self.async_step_user()

    async def async_step_reauth(self, _) -> FlowResult:
        """Handle initial step when updating invalid credentials."""
        self._reauth_entry = self.hass.config_entries.async_get_entry(
            self.context["entry_id"]
        )
        assert self._reauth_entry is not None
        self.context["title_placeholders"] = {
            CONF_HOST: self._reauth_entry.data[CONF_HOST],
        }
        self.discovery_schema = _schema_with_defaults(
            host=self._reauth_entry.data[CONF_HOST],
            port=self._reauth_entry.data[CONF_PORT],
            ssl=self._reauth_entry.data[CONF_SSL],
        )

        self.context["identifier"] = self.unique_id
        return await self.async_step_user()


class CannotConnect(HomeAssistantError):
    """Error to indicate we cannot connect."""


class InvalidAuth(HomeAssistantError):
    """Error to indicate there is invalid auth."""
