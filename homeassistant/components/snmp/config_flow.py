"""Config flow for SNMP."""

from __future__ import annotations

import logging
from typing import Any

from pysnmp.error import PySnmpError
import pysnmp.hlapi.v3arch.asyncio as hlapi
from pysnmp.hlapi.v3arch.asyncio import (
    CommunityData,
    Udp6TransportTarget,
    UdpTransportTarget,
    UsmUserData,
    get_cmd,
)
import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_HOST, CONF_PORT, CONF_USERNAME
from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_validation as cv

from .const import (
    CONF_AUTH_KEY,
    CONF_AUTH_PROTOCOL,
    CONF_BASEOID,
    CONF_COMMUNITY,
    CONF_PRIV_KEY,
    CONF_PRIV_PROTOCOL,
    CONF_VERSION,
    DEFAULT_AUTH_PROTOCOL,
    DEFAULT_COMMUNITY,
    DEFAULT_PORT,
    DEFAULT_PRIV_PROTOCOL,
    DEFAULT_VERSION,
    DOMAIN,
    MAP_AUTH_PROTOCOLS,
    MAP_PRIV_PROTOCOLS,
    SNMP_VERSIONS,
)
from .util import async_create_request_cmd_args

_LOGGER = logging.getLogger(__name__)


STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_HOST): str,
        vol.Optional(CONF_PORT, default=int(DEFAULT_PORT)): cv.port,
        vol.Required(CONF_BASEOID): str,
        vol.Optional(CONF_COMMUNITY, default=DEFAULT_COMMUNITY): str,
        vol.Optional(CONF_VERSION, default=DEFAULT_VERSION): vol.In(
            list(SNMP_VERSIONS)
        ),
        vol.Optional(CONF_USERNAME): str,
        vol.Optional(CONF_AUTH_KEY): str,
        vol.Optional(CONF_AUTH_PROTOCOL, default=DEFAULT_AUTH_PROTOCOL): vol.In(
            list(MAP_AUTH_PROTOCOLS)
        ),
        vol.Optional(CONF_PRIV_KEY): str,
        vol.Optional(CONF_PRIV_PROTOCOL, default=DEFAULT_PRIV_PROTOCOL): vol.In(
            list(MAP_PRIV_PROTOCOLS)
        ),
    }
)


async def validate_input(hass: HomeAssistant, data: dict[str, Any]) -> None:
    """Validate the user input allows us to connect.

    Data has the keys from STEP_USER_DATA_SCHEMA with values provided by the user.
    """
    host = data[CONF_HOST]
    port = int(data.get(CONF_PORT, DEFAULT_PORT))
    community = data.get(CONF_COMMUNITY, DEFAULT_COMMUNITY)
    version = data.get(CONF_VERSION, DEFAULT_VERSION)
    baseoid = data[CONF_BASEOID]
    username = data.get(CONF_USERNAME)
    authkey = data.get(CONF_AUTH_KEY)
    authproto = data.get(CONF_AUTH_PROTOCOL, DEFAULT_AUTH_PROTOCOL)
    privkey = data.get(CONF_PRIV_KEY)
    privproto = data.get(CONF_PRIV_PROTOCOL, DEFAULT_PRIV_PROTOCOL)

    try:
        target = await UdpTransportTarget.create((host, port))
    except PySnmpError:
        try:
            target = Udp6TransportTarget((host, port))
        except PySnmpError:
            raise CannotConnect from None

    if version == "3":
        if not authkey:
            authproto = "none"
        if not privkey:
            privproto = "none"

        auth_data = UsmUserData(
            username,
            authKey=authkey or None,
            privKey=privkey or None,
            authProtocol=getattr(hlapi, MAP_AUTH_PROTOCOLS[authproto]),
            privProtocol=getattr(hlapi, MAP_PRIV_PROTOCOLS[privproto]),
        )
    else:
        auth_data = CommunityData(community, mpModel=SNMP_VERSIONS[version])

    request_args = await async_create_request_cmd_args(hass, auth_data, target, baseoid)

    err_indication, err_status, _, _ = await get_cmd(*request_args)

    if err_indication:
        raise CannotConnect(err_indication) from None
    if err_status:
        raise InvalidAuth(err_status.prettyPrint()) from None


class SnmpConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for SNMP."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step."""
        errors: dict[str, str] = {}

        if user_input is not None:
            if user_input.get(CONF_PRIV_KEY) and not user_input.get(CONF_AUTH_KEY):
                errors["base"] = "auth_key_required_for_priv"

            if not errors:
                try:
                    await validate_input(self.hass, user_input)
                except CannotConnect:
                    errors["base"] = "cannot_connect"
                except InvalidAuth:
                    errors["base"] = "invalid_auth"
                except Exception:
                    _LOGGER.exception("Unexpected exception")
                    errors["base"] = "unknown"
                else:
                    return self.async_create_entry(
                        title=user_input[CONF_HOST], data=user_input
                    )

        return self.async_show_form(
            step_id="user",
            data_schema=STEP_USER_DATA_SCHEMA,
            errors=errors,
        )

    async def async_step_import(self, user_input: dict[str, Any]) -> ConfigFlowResult:
        """Handle import from the old YAML configuration file."""
        for entry in self._async_current_entries():
            if entry.data.get(CONF_HOST) == user_input.get(
                CONF_HOST
            ) and entry.data.get(CONF_BASEOID) == user_input.get(CONF_BASEOID):
                return self.async_abort(reason="already_configured")

        # Filter to only include keys that are relevant to SNMP config entries.
        # The legacy platform schema adds extra keys (platform, consider_home,
        # new_device_defaults) that are not serializable or not needed.
        allowed_keys = {
            CONF_HOST,
            CONF_PORT,
            CONF_BASEOID,
            CONF_COMMUNITY,
            CONF_VERSION,
            CONF_USERNAME,
            CONF_AUTH_KEY,
            CONF_AUTH_PROTOCOL,
            CONF_PRIV_KEY,
            CONF_PRIV_PROTOCOL,
        }
        clean_data = {k: v for k, v in user_input.items() if k in allowed_keys}

        return self.async_create_entry(title=clean_data[CONF_HOST], data=clean_data)


class CannotConnect(Exception):
    """Error to indicate we cannot connect."""


class InvalidAuth(Exception):
    """Error to indicate there is invalid auth."""
