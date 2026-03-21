"""Config flow for SNMP."""

from __future__ import annotations

import logging
from typing import Any

from pysnmp.error import PySnmpError
import pysnmp.hlapi.v3arch.asyncio as hlapi
from pysnmp.hlapi.v3arch.asyncio import (
    CommunityData,
    ObjectIdentity,
    Udp6TransportTarget,
    UdpTransportTarget,
    UsmUserData,
    get_cmd,
)
from pysnmp.smi.error import WrongValueError
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
    CONF_CONTEXT_NAME,
    CONF_IMPORTED_BY,
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
        vol.Optional(CONF_VERSION, default=DEFAULT_VERSION): vol.In(
            list(SNMP_VERSIONS)
        ),
    }
)

STEP_V1_V2C_DATA_SCHEMA = vol.Schema(
    {
        vol.Optional(CONF_COMMUNITY, default=DEFAULT_COMMUNITY): str,
    }
)

STEP_V3_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_USERNAME): str,
        vol.Optional(CONF_AUTH_KEY): str,
        vol.Optional(CONF_AUTH_PROTOCOL, default=DEFAULT_AUTH_PROTOCOL): vol.In(
            list(MAP_AUTH_PROTOCOLS)
        ),
        vol.Optional(CONF_PRIV_KEY): str,
        vol.Optional(CONF_PRIV_PROTOCOL, default=DEFAULT_PRIV_PROTOCOL): vol.In(
            list(MAP_PRIV_PROTOCOLS)
        ),
        vol.Optional(CONF_CONTEXT_NAME): str,
    }
)


async def validate_input(hass: HomeAssistant, data: dict[str, Any]) -> None:
    """Validate the user input allows us to connect."""
    host = data[CONF_HOST]
    port = int(data.get(CONF_PORT, DEFAULT_PORT))
    community = data.get(CONF_COMMUNITY, DEFAULT_COMMUNITY)
    version = data.get(CONF_VERSION, DEFAULT_VERSION)
    username = data.get(CONF_USERNAME)
    authkey = data.get(CONF_AUTH_KEY)
    authproto = data.get(CONF_AUTH_PROTOCOL, DEFAULT_AUTH_PROTOCOL)
    privkey = data.get(CONF_PRIV_KEY)
    privproto = data.get(CONF_PRIV_PROTOCOL, DEFAULT_PRIV_PROTOCOL)
    context_name = data.get(CONF_CONTEXT_NAME)

    try:
        target = await UdpTransportTarget.create((host, port))
    except PySnmpError as err1:
        try:
            target = await Udp6TransportTarget.create((host, port))
        except PySnmpError as err2:
            raise CannotConnect(f"{err1} / {err2}") from None
    except Exception as err:  # pylint: disable=broad-except
        _LOGGER.exception("Unexpected error during SNMP target creation")
        raise CannotConnect(str(err)) from None

    try:
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
    except PySnmpError as err:
        raise InvalidAuth(str(err)) from None

    # Use sysDescr.0 to verify connectivity and authentication.
    # This OID is standard and responds to GET on almost all devices.
    # This avoids false InvalidAuth errors if baseoid is a table or node.
    test_oid = "1.3.6.1.2.1.1.1.0"
    request_args = await async_create_request_cmd_args(
        hass, auth_data, target, test_oid, context_name
    )

    try:
        err_indication, err_status, _, _ = await get_cmd(*request_args)
    except WrongValueError:
        # pysnmp raises WrongValueError when v3 credentials/keys match the wrong protocol
        raise InvalidAuth("Invalid authentication credentials or protocols") from None
    except PySnmpError as err:
        # Handle other pysnmp errors like StatusInformation/SerializationError
        raise CannotConnect(str(err)) from None

    if err_indication:
        raise CannotConnect(str(err_indication)) from None

    if version == "3" and err_status:
        raise InvalidAuth(err_status.prettyPrint()) from None

    # Also verify that the user-provided baseoid is serializable and valid.
    # This catches errors like "Short OID 1" during the config flow.
    base_oid = data[CONF_BASEOID]
    base_request_args = await async_create_request_cmd_args(
        hass, auth_data, target, base_oid, context_name
    )
    try:
        # We don't necessarily care about the result, just that it serializes and sends.
        await get_cmd(*base_request_args)
    except (PySnmpError, WrongValueError) as err:
        raise CannotConnect(f"Invalid OID '{base_oid}': {err}") from None

    # In v1/v2c, getting ANY response (even noSuchName in err_status)
    # means the community string is correct. Silence means auth failure (v1/v2c).
    # In v3, err_status indicates the success of the get_cmd itself.
    if version != "3":
        return

    if err_status:
        raise InvalidAuth(err_status.prettyPrint()) from None


class SnmpConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for SNMP."""

    VERSION = 1
    _user_data: dict[str, Any]

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step."""
        errors: dict[str, str] = {}
        if user_input is not None:
            try:
                ObjectIdentity(user_input[CONF_BASEOID])
            except Exception:  # pylint: disable=broad-except # noqa: BLE001
                errors["baseoid"] = "invalid_oid"
            else:
                self._user_data = user_input
                if user_input[CONF_VERSION] == "3":
                    return await self.async_step_v3()
                return await self.async_step_v1_v2c()

        return self.async_show_form(
            step_id="user",
            data_schema=self.add_suggested_values_to_schema(
                STEP_USER_DATA_SCHEMA, user_input or getattr(self, "_user_data", None)
            ),
            errors=errors,
            last_step=False,
        )

    async def async_step_v1_v2c(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle V1/V2c authentication."""
        errors: dict[str, str] = {}
        description_placeholders: dict[str, str] = {}
        if user_input is not None:
            data = {**self._user_data, **user_input}
            try:
                await validate_input(self.hass, data)
            except CannotConnect as err:
                errors["base"] = "cannot_connect"
                description_placeholders["error"] = str(err)
            except InvalidAuth as err:
                errors["base"] = "invalid_auth"
                description_placeholders["error"] = str(err)
            except Exception as err:  # pylint: disable=broad-except
                _LOGGER.exception("Unexpected exception")
                errors["base"] = "unknown"
                description_placeholders["error"] = str(err)
            else:
                return self.async_create_entry(title=data[CONF_HOST], data=data)

        return self.async_show_form(
            step_id="v1_v2c",
            data_schema=self.add_suggested_values_to_schema(
                STEP_V1_V2C_DATA_SCHEMA, user_input
            ),
            errors=errors,
            description_placeholders=description_placeholders,
        )

    async def async_step_v3(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle V3 authentication."""
        errors: dict[str, str] = {}
        description_placeholders: dict[str, str] = {}
        if user_input is not None:
            if user_input.get(CONF_PRIV_KEY) and not user_input.get(CONF_AUTH_KEY):
                errors["base"] = "auth_key_required_for_priv"

            if not errors:
                data = {**self._user_data, **user_input}
                try:
                    await validate_input(self.hass, data)
                except CannotConnect as err:
                    errors["base"] = "cannot_connect"
                    description_placeholders["error"] = str(err)
                except InvalidAuth as err:
                    errors["base"] = "invalid_auth"
                    description_placeholders["error"] = str(err)
                except Exception as err:  # pylint: disable=broad-except
                    _LOGGER.exception("Unexpected exception")
                    errors["base"] = "unknown"
                    description_placeholders["error"] = str(err)
                else:
                    return self.async_create_entry(title=data[CONF_HOST], data=data)

        return self.async_show_form(
            step_id="v3",
            data_schema=self.add_suggested_values_to_schema(
                STEP_V3_DATA_SCHEMA, user_input
            ),
            errors=errors,
            description_placeholders=description_placeholders,
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
            CONF_CONTEXT_NAME,
            CONF_VERSION,
            CONF_USERNAME,
            CONF_AUTH_KEY,
            CONF_AUTH_PROTOCOL,
            CONF_PRIV_KEY,
            CONF_PRIV_PROTOCOL,
        }
        clean_data = {k: v for k, v in user_input.items() if k in allowed_keys}
        # Track that this config entry was imported from YAML device_tracker
        clean_data[CONF_IMPORTED_BY] = "device_tracker"

        return self.async_create_entry(title=clean_data[CONF_HOST], data=clean_data)


class CannotConnect(Exception):
    """Error to indicate we cannot connect."""


class InvalidAuth(Exception):
    """Error to indicate there is invalid auth."""
