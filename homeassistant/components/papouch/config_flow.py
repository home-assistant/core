"""Config flow for the Papouch integration."""

import ipaddress
from typing import Any, override

import aiohttp
from aiopapouch import PapouchHTTPClient
from aiopapouch.exceptions import (
    DeviceAuthError,
    DeviceConnectionError,
    DeviceLogicError,
)
import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_IP_ADDRESS, CONF_PASSWORD, CONF_PORT
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.device_registry import format_mac

from .const import DEFAULT_WEB_PORT, DOMAIN
from .utils import _get_device_name

WEB_MODE_INDEX = 3


class PapouchConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Papouch."""

    def __init__(self) -> None:
        """Initialize the config flow."""
        self._saved_input: dict | None = None
        self.discovered_ip: str | None = None

    async def _test_connection(
        self, ip_address: str, password: str = "", web_port: int = DEFAULT_WEB_PORT
    ) -> tuple[dict[str, str], int | None]:
        """Test the connection and return any errors and the device mode."""
        try:
            ipaddress.ip_address(ip_address)
        except ValueError:
            return {CONF_IP_ADDRESS: "invalid_ip_format"}, None

        session = async_get_clientsession(self.hass)
        client = PapouchHTTPClient(
            ip_address, session, password=password, web_port=web_port
        )

        try:
            await client.fetch_info()
            mode_device = await client.get_device_mode()
        except DeviceAuthError:
            return {"base": "invalid_auth"}, None
        except (
            aiohttp.ClientError,
            DeviceConnectionError,
            TimeoutError,
        ):
            return {"base": "cannot_connect"}, None
        else:
            return {}, mode_device

    async def _async_process_user_input(
        self, user_input: dict[str, Any]
    ) -> tuple[dict[str, str], ConfigFlowResult | None]:
        """Process user input, test connection, and determine the next routing step."""
        self._async_abort_entries_match({CONF_IP_ADDRESS: user_input[CONF_IP_ADDRESS]})

        ip_address = user_input[CONF_IP_ADDRESS]

        password = user_input.get(CONF_PASSWORD)
        if password == "":
            password = None

        web_port = int(user_input[CONF_PORT])

        errors, mode_device = await self._test_connection(
            user_input[CONF_IP_ADDRESS], password or "", web_port
        )

        if errors:
            return errors, None

        self._saved_input = user_input

        if mode_device == -1:
            return {}, self.async_abort(reason="mode_is_missing")
        if mode_device != WEB_MODE_INDEX:
            return {}, self.async_abort(reason="web_mode_required")

        session = async_get_clientsession(self.hass)
        client = PapouchHTTPClient(
            ip_address,
            session,
            password=password or "",
            web_port=web_port,
        )
        title_name = await _get_device_name(self.hass, ip_address, password or "")

        try:
            mac_address = await client.get_device_mac()
        except DeviceAuthError:
            errors["base"] = "invalid_auth"
        except aiohttp.ClientError, DeviceLogicError:
            errors["base"] = "cannot_connect"

        if errors:
            return errors, None

        formatted_mac = format_mac(mac_address)
        await self.async_set_unique_id(formatted_mac)
        self._abort_if_unique_id_configured()

        data = {
            CONF_IP_ADDRESS: user_input[CONF_IP_ADDRESS],
            CONF_PASSWORD: password,
            "device_name": title_name,
            CONF_PORT: web_port,
        }

        return {}, self.async_create_entry(
            title=f"{title_name} - {user_input[CONF_IP_ADDRESS]}", data=data
        )

    @override
    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the first step in config flow."""
        errors: dict[str, str] = {}

        if user_input is not None:
            errors, result = await self._async_process_user_input(user_input)
            if result:
                return result

        default_ip = self.discovered_ip or ""
        default_web_port = DEFAULT_WEB_PORT

        if user_input and CONF_IP_ADDRESS in user_input:
            default_ip = user_input[CONF_IP_ADDRESS]
        if user_input and CONF_PORT in user_input:
            default_web_port = user_input[CONF_PORT]

        schema = vol.Schema(
            {
                vol.Required(CONF_IP_ADDRESS, default=default_ip): str,
                vol.Optional(CONF_PORT, default=default_web_port): vol.All(
                    int, vol.Range(min=1, max=65536)
                ),
                vol.Optional(CONF_PASSWORD): str,
            }
        )

        return self.async_show_form(
            step_id="user",
            data_schema=schema,
            errors=errors,
        )
