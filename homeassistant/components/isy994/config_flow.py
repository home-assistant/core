"""Config flow for Universal Devices ISY/IoX integration."""

from __future__ import annotations

import asyncio
from collections.abc import Mapping
import logging
from typing import Any
from urllib.parse import urlparse, urlunparse

from aiohttp import CookieJar
from pyisy import ISYConnectionError, ISYInvalidAuthError, ISYResponseParseError
from pyisy.configuration import Configuration
from pyisy.connection import Connection
import voluptuous as vol

from homeassistant.components import dhcp, ssdp
from homeassistant.config_entries import (
    SOURCE_IGNORE,
    ConfigEntry,
    ConfigFlow,
    ConfigFlowResult,
    OptionsFlow,
)
from homeassistant.const import CONF_HOST, CONF_NAME, CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant, callback
from homeassistant.data_entry_flow import AbortFlow
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import aiohttp_client

from .const import (
    CONF_IGNORE_STRING,
    CONF_RESTORE_LIGHT_STATE,
    CONF_SENSOR_STRING,
    CONF_TLS_VER,
    CONF_VAR_SENSOR_STRING,
    DEFAULT_IGNORE_STRING,
    DEFAULT_RESTORE_LIGHT_STATE,
    DEFAULT_SENSOR_STRING,
    DEFAULT_TLS_VERSION,
    DEFAULT_VAR_SENSOR_STRING,
    DOMAIN,
    HTTP_PORT,
    HTTPS_PORT,
    ISY_CONF_NAME,
    ISY_CONF_UUID,
    ISY_URL_POSTFIX,
    SCHEME_HTTP,
    SCHEME_HTTPS,
    UDN_UUID_PREFIX,
)

_LOGGER = logging.getLogger(__name__)


def _data_schema(schema_input: dict[str, str]) -> vol.Schema:
    """Generate schema with defaults."""
    return vol.Schema(
        {
            vol.Required(CONF_HOST, default=schema_input.get(CONF_HOST, "")): str,
            vol.Required(CONF_USERNAME): str,
            vol.Required(CONF_PASSWORD): str,
            vol.Optional(CONF_TLS_VER, default=DEFAULT_TLS_VERSION): vol.In([1.1, 1.2]),
        },
        extra=vol.ALLOW_EXTRA,
    )


async def validate_input(hass: HomeAssistant, data: dict[str, Any]) -> dict[str, str]:
    """Validate the user input allows us to connect.

    Data has the keys from DATA_SCHEMA with values provided by the user.
    """
    user = data[CONF_USERNAME]
    password = data[CONF_PASSWORD]
    host = urlparse(data[CONF_HOST])
    tls_version = data.get(CONF_TLS_VER)

    if host.scheme == SCHEME_HTTP:
        https = False
        port = host.port or HTTP_PORT
        session = aiohttp_client.async_create_clientsession(
            hass, verify_ssl=False, cookie_jar=CookieJar(unsafe=True)
        )
    elif host.scheme == SCHEME_HTTPS:
        https = True
        port = host.port or HTTPS_PORT
        session = aiohttp_client.async_get_clientsession(hass)
    else:
        _LOGGER.error("The ISY/IoX host value in configuration is invalid")
        raise InvalidHost

    # Connect to ISY controller.
    isy_conn = Connection(
        host.hostname,
        port,
        user,
        password,
        use_https=https,
        tls_ver=tls_version,
        webroot=host.path,
        websession=session,
    )

    try:
        async with asyncio.timeout(30):
            isy_conf_xml = await isy_conn.test_connection()
    except ISYInvalidAuthError as error:
        raise InvalidAuth from error
    except ISYConnectionError as error:
        raise CannotConnect from error

    try:
        isy_conf = Configuration(xml=isy_conf_xml)
    except ISYResponseParseError as error:
        raise CannotConnect from error
    if not isy_conf or ISY_CONF_NAME not in isy_conf or not isy_conf[ISY_CONF_NAME]:
        raise CannotConnect

    # Return info that you want to store in the config entry.
    return {
        "title": f"{isy_conf[ISY_CONF_NAME]} ({host.hostname})",
        ISY_CONF_UUID: isy_conf[ISY_CONF_UUID],
    }


class Isy994ConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Universal Devices ISY/IoX."""

    VERSION = 1

    def __init__(self) -> None:
        """Initialize the ISY/IoX config flow."""
        self.discovered_conf: dict[str, str] = {}
        self._existing_entry: ConfigEntry | None = None

    @staticmethod
    @callback
    def async_get_options_flow(
        config_entry: ConfigEntry,
    ) -> OptionsFlow:
        """Get the options flow for this handler."""
        return OptionsFlowHandler(config_entry)

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step."""
        errors = {}
        info: dict[str, str] = {}
        if user_input is not None:
            try:
                info = await validate_input(self.hass, user_input)
            except CannotConnect:
                errors["base"] = "cannot_connect"
            except InvalidHost:
                errors["base"] = "invalid_host"
            except InvalidAuth:
                errors[CONF_PASSWORD] = "invalid_auth"
            except Exception:  # pylint: disable=broad-except
                _LOGGER.exception("Unexpected exception")
                errors["base"] = "unknown"

            if not errors:
                await self.async_set_unique_id(
                    info[ISY_CONF_UUID], raise_on_progress=False
                )
                self._abort_if_unique_id_configured()
                return self.async_create_entry(title=info["title"], data=user_input)

        return self.async_show_form(
            step_id="user",
            data_schema=_data_schema(self.discovered_conf),
            errors=errors,
        )

    async def _async_set_unique_id_or_update(
        self, isy_mac: str, ip_address: str, port: int | None
    ) -> None:
        """Abort and update the ip address on change."""
        existing_entry = await self.async_set_unique_id(isy_mac)
        if not existing_entry:
            return
        if existing_entry.source == SOURCE_IGNORE:
            raise AbortFlow("already_configured")
        parsed_url = urlparse(existing_entry.data[CONF_HOST])
        if parsed_url.hostname != ip_address:
            new_netloc = ip_address
            if port:
                new_netloc = f"{ip_address}:{port}"
            elif parsed_url.port:
                new_netloc = f"{ip_address}:{parsed_url.port}"
            self.hass.config_entries.async_update_entry(
                existing_entry,
                data={
                    **existing_entry.data,
                    CONF_HOST: urlunparse(
                        (
                            parsed_url.scheme,
                            new_netloc,
                            parsed_url.path,
                            parsed_url.query,
                            parsed_url.fragment,
                            None,
                        )
                    ),
                },
            )
        raise AbortFlow("already_configured")

    async def async_step_dhcp(
        self, discovery_info: dhcp.DhcpServiceInfo
    ) -> ConfigFlowResult:
        """Handle a discovered ISY/IoX device via dhcp."""
        friendly_name = discovery_info.hostname
        if friendly_name.startswith(("polisy", "eisy")):
            url = f"http://{discovery_info.ip}:8080"
        else:
            url = f"http://{discovery_info.ip}"
        mac = discovery_info.macaddress
        isy_mac = (
            f"{mac[0:2]}:{mac[2:4]}:{mac[4:6]}:{mac[6:8]}:{mac[8:10]}:{mac[10:12]}"
        )
        await self._async_set_unique_id_or_update(isy_mac, discovery_info.ip, None)

        self.discovered_conf = {
            CONF_NAME: friendly_name,
            CONF_HOST: url,
        }

        self.context["title_placeholders"] = self.discovered_conf
        return await self.async_step_user()

    async def async_step_ssdp(
        self, discovery_info: ssdp.SsdpServiceInfo
    ) -> ConfigFlowResult:
        """Handle a discovered ISY/IoX Device."""
        friendly_name = discovery_info.upnp[ssdp.ATTR_UPNP_FRIENDLY_NAME]
        url = discovery_info.ssdp_location
        assert isinstance(url, str)
        parsed_url = urlparse(url)
        mac = discovery_info.upnp[ssdp.ATTR_UPNP_UDN]
        mac = mac.removeprefix(UDN_UUID_PREFIX)
        url = url.removesuffix(ISY_URL_POSTFIX)

        port = HTTP_PORT
        if parsed_url.port:
            port = parsed_url.port
        elif parsed_url.scheme == SCHEME_HTTPS:
            port = HTTPS_PORT

        assert isinstance(parsed_url.hostname, str)
        await self._async_set_unique_id_or_update(mac, parsed_url.hostname, port)

        self.discovered_conf = {
            CONF_NAME: friendly_name,
            CONF_HOST: url,
        }

        self.context["title_placeholders"] = self.discovered_conf
        return await self.async_step_user()

    async def async_step_reauth(
        self, entry_data: Mapping[str, Any]
    ) -> ConfigFlowResult:
        """Handle reauth."""
        self._existing_entry = await self.async_set_unique_id(self.context["unique_id"])
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle reauth input."""
        errors = {}
        assert self._existing_entry is not None
        existing_entry = self._existing_entry
        existing_data = existing_entry.data
        if user_input is not None:
            new_data = {
                **existing_data,
                CONF_USERNAME: user_input[CONF_USERNAME],
                CONF_PASSWORD: user_input[CONF_PASSWORD],
            }
            try:
                await validate_input(self.hass, new_data)
            except CannotConnect:
                errors["base"] = "cannot_connect"
            except InvalidAuth:
                errors[CONF_PASSWORD] = "invalid_auth"
            else:
                return self.async_update_reload_and_abort(
                    self._existing_entry, data=new_data
                )

        self.context["title_placeholders"] = {
            CONF_NAME: existing_entry.title,
            CONF_HOST: existing_data[CONF_HOST],
        }
        return self.async_show_form(
            description_placeholders={CONF_HOST: existing_data[CONF_HOST]},
            step_id="reauth_confirm",
            data_schema=vol.Schema(
                {
                    vol.Required(
                        CONF_USERNAME, default=existing_data[CONF_USERNAME]
                    ): str,
                    vol.Required(CONF_PASSWORD): str,
                }
            ),
            errors=errors,
        )


class OptionsFlowHandler(OptionsFlow):
    """Handle a option flow for ISY/IoX."""

    def __init__(self, config_entry: ConfigEntry) -> None:
        """Initialize options flow."""
        self.config_entry = config_entry

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle options flow."""
        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)

        options = self.config_entry.options
        restore_light_state = options.get(
            CONF_RESTORE_LIGHT_STATE, DEFAULT_RESTORE_LIGHT_STATE
        )
        ignore_string = options.get(CONF_IGNORE_STRING, DEFAULT_IGNORE_STRING)
        sensor_string = options.get(CONF_SENSOR_STRING, DEFAULT_SENSOR_STRING)
        var_sensor_string = options.get(
            CONF_VAR_SENSOR_STRING, DEFAULT_VAR_SENSOR_STRING
        )

        options_schema = vol.Schema(
            {
                vol.Optional(CONF_IGNORE_STRING, default=ignore_string): str,
                vol.Optional(CONF_SENSOR_STRING, default=sensor_string): str,
                vol.Optional(CONF_VAR_SENSOR_STRING, default=var_sensor_string): str,
                vol.Required(
                    CONF_RESTORE_LIGHT_STATE, default=restore_light_state
                ): bool,
            }
        )

        return self.async_show_form(step_id="init", data_schema=options_schema)


class InvalidHost(HomeAssistantError):
    """Error to indicate the host value is invalid."""


class CannotConnect(HomeAssistantError):
    """Error to indicate we cannot connect."""


class InvalidAuth(HomeAssistantError):
    """Error to indicate there is invalid auth."""
