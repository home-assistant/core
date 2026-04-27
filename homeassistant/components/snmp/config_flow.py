"""Config flow for SNMP."""

from __future__ import annotations

import logging
from typing import Any

from pysnmp.error import PySnmpError
from pysnmp.hlapi.v3arch.asyncio import ObjectIdentity, get_cmd
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
    DEFAULT_TIMEOUT,
    DEFAULT_VERSION,
    DOMAIN,
    MAP_AUTH_PROTOCOLS,
    MAP_PRIV_PROTOCOLS,
    SNMP_VERSIONS,
)
from .util import (
    async_create_request_cmd_args,
    async_create_transport_target,
    create_auth_data,
)

_LOGGER = logging.getLogger(__name__)


STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_HOST): str,
        vol.Optional(CONF_PORT, default=DEFAULT_PORT): cv.port,
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
    port = data.get(CONF_PORT, DEFAULT_PORT)
    version = data.get(CONF_VERSION, DEFAULT_VERSION)
    context_name = data.get(CONF_CONTEXT_NAME)

    try:
        target = await async_create_transport_target(host, port, DEFAULT_TIMEOUT)
    except PySnmpError as err:
        _LOGGER.warning("SNMP target creation failed: %s", err)
        raise CannotConnect(f"SNMP target creation failed: {err}") from err

    try:
        auth_data = create_auth_data(data, version)
    except PySnmpError as err:
        raise InvalidAuth(str(err)) from err

    # Use sysDescr.0 to verify connectivity and authentication.
    # This OID is standard and responds to GET on almost all devices.
    # This avoids false InvalidAuth errors if baseoid is a table or node.
    test_oid = "1.3.6.1.2.1.1.1.0"
    request_args = await async_create_request_cmd_args(
        hass, auth_data, target, test_oid, context_name
    )

    try:
        err_indication, err_status, _, _ = await get_cmd(*request_args)
    except WrongValueError as err:
        # pysnmp raises WrongValueError when v3 credentials/keys match the wrong protocol
        raise InvalidAuth("Invalid authentication credentials or protocols") from err
    except PySnmpError as err:
        # Handle other pysnmp errors like StatusInformation/SerializationError
        raise CannotConnect(str(err)) from err

    if err_indication:
        raise CannotConnect(str(err_indication))

    if version == "3" and err_status:
        raise InvalidAuth(err_status.prettyPrint())

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
        raise CannotConnect(f"Invalid OID '{base_oid}': {err}") from err


class SnmpConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for SNMP."""

    VERSION = 1
    MINOR_VERSION = 1
    _user_data: dict[str, Any]

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step."""
        errors: dict[str, str] = {}
        if user_input is not None:
            try:
                ObjectIdentity(user_input[CONF_BASEOID])
            except PySnmpError:
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
            if result := await self._async_validate_and_create_entry(
                data, errors, description_placeholders
            ):
                return result

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
                if result := await self._async_validate_and_create_entry(
                    data, errors, description_placeholders
                ):
                    return result

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
        await self._async_check_unique_id(user_input)

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

    async def _async_check_unique_id(self, user_input: dict[str, Any]) -> None:
        """Set the unique ID and abort if already configured."""
        port = user_input.get(CONF_PORT, DEFAULT_PORT)
        context_name = user_input.get(CONF_CONTEXT_NAME)
        unique_id = f"{user_input[CONF_HOST]}_{port}_{user_input[CONF_BASEOID]}"
        if context_name:
            unique_id = f"{unique_id}_{context_name}"
        await self.async_set_unique_id(unique_id)
        self._abort_if_unique_id_configured()

    async def _async_validate_and_create_entry(
        self,
        data: dict[str, Any],
        errors: dict[str, str],
        description_placeholders: dict[str, str],
    ) -> ConfigFlowResult | None:
        """Validate input and create entry."""
        await self._async_check_unique_id(data)
        try:
            await validate_input(self.hass, data)
        except CannotConnect as err:
            errors["base"] = "cannot_connect"
            description_placeholders["error"] = str(err)
        except InvalidAuth as err:
            errors["base"] = "invalid_auth"
            description_placeholders["error"] = str(err)
        except PySnmpError as err:
            _LOGGER.warning("Unexpected SNMP error during validation: %s", err)
            errors["base"] = "cannot_connect"
            description_placeholders["error"] = str(err)
        else:
            return self.async_create_entry(title=data[CONF_HOST], data=data)
        return None


class CannotConnect(Exception):
    """Error to indicate we cannot connect."""


class InvalidAuth(Exception):
    """Error to indicate there is invalid auth."""
