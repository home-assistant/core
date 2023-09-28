"""ISY Services and Commands."""
from __future__ import annotations

from typing import Any

from pyisy.constants import COMMAND_FRIENDLY_NAME
import voluptuous as vol

from homeassistant.const import (
    CONF_ADDRESS,
    CONF_COMMAND,
    CONF_NAME,
    CONF_UNIT_OF_MEASUREMENT,
)
from homeassistant.core import HomeAssistant, ServiceCall, callback
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.entity_platform import async_get_platforms
from homeassistant.helpers.service import entity_service_call

from .const import _LOGGER, DOMAIN

# Common Services for All Platforms:
SERVICE_SEND_PROGRAM_COMMAND = "send_program_command"

# Entity specific methods (valid for most Groups/ISY Scenes, Lights, Switches, Fans)
SERVICE_SEND_RAW_NODE_COMMAND = "send_raw_node_command"
SERVICE_SEND_NODE_COMMAND = "send_node_command"
SERVICE_GET_ZWAVE_PARAMETER = "get_zwave_parameter"
SERVICE_SET_ZWAVE_PARAMETER = "set_zwave_parameter"
SERVICE_RENAME_NODE = "rename_node"

# Services valid only for Z-Wave Locks
SERVICE_SET_ZWAVE_LOCK_USER_CODE = "set_zwave_lock_user_code"
SERVICE_DELETE_ZWAVE_LOCK_USER_CODE = "delete_zwave_lock_user_code"

CONF_PARAMETER = "parameter"
CONF_PARAMETERS = "parameters"
CONF_USER_NUM = "user_num"
CONF_CODE = "code"
CONF_VALUE = "value"
CONF_INIT = "init"
CONF_ISY = "isy"
CONF_SIZE = "size"

VALID_NODE_COMMANDS = [
    "beep",
    "brighten",
    "dim",
    "disable",
    "enable",
    "fade_down",
    "fade_stop",
    "fade_up",
    "fast_off",
    "fast_on",
    "query",
]
VALID_PROGRAM_COMMANDS = [
    "run",
    "run_then",
    "run_else",
    "stop",
    "enable",
    "disable",
    "enable_run_at_startup",
    "disable_run_at_startup",
]
VALID_PARAMETER_SIZES = [1, 2, 4]


def valid_isy_commands(value: Any) -> str:
    """Validate the command is valid."""
    value = str(value).upper()
    if value in COMMAND_FRIENDLY_NAME:
        assert isinstance(value, str)
        return value
    raise vol.Invalid("Invalid ISY Command.")


SCHEMA_GROUP = "name-address"

SERVICE_SEND_RAW_NODE_COMMAND_SCHEMA = {
    vol.Required(CONF_COMMAND): vol.All(cv.string, valid_isy_commands),
    vol.Optional(CONF_VALUE): vol.All(vol.Coerce(int), vol.Range(0, 255)),
    vol.Optional(CONF_UNIT_OF_MEASUREMENT): vol.All(vol.Coerce(int), vol.Range(0, 120)),
    vol.Optional(CONF_PARAMETERS, default={}): {cv.string: cv.string},
}

SERVICE_SEND_NODE_COMMAND_SCHEMA = {
    vol.Required(CONF_COMMAND): vol.In(VALID_NODE_COMMANDS)
}

SERVICE_RENAME_NODE_SCHEMA = {vol.Required(CONF_NAME): cv.string}

SERVICE_GET_ZWAVE_PARAMETER_SCHEMA = {vol.Required(CONF_PARAMETER): vol.Coerce(int)}

SERVICE_SET_ZWAVE_PARAMETER_SCHEMA = {
    vol.Required(CONF_PARAMETER): vol.Coerce(int),
    vol.Required(CONF_VALUE): vol.Coerce(int),
    vol.Required(CONF_SIZE): vol.All(vol.Coerce(int), vol.In(VALID_PARAMETER_SIZES)),
}

SERVICE_SET_USER_CODE_SCHEMA = {
    vol.Required(CONF_USER_NUM): vol.Coerce(int),
    vol.Required(CONF_CODE): vol.Coerce(int),
}

SERVICE_DELETE_USER_CODE_SCHEMA = {vol.Required(CONF_USER_NUM): vol.Coerce(int)}

SERVICE_SEND_PROGRAM_COMMAND_SCHEMA = vol.All(
    cv.has_at_least_one_key(CONF_ADDRESS, CONF_NAME),
    vol.Schema(
        {
            vol.Exclusive(CONF_NAME, SCHEMA_GROUP): cv.string,
            vol.Exclusive(CONF_ADDRESS, SCHEMA_GROUP): cv.string,
            vol.Required(CONF_COMMAND): vol.In(VALID_PROGRAM_COMMANDS),
            vol.Optional(CONF_ISY): cv.string,
        }
    ),
)


@callback
def async_setup_services(hass: HomeAssistant) -> None:  # noqa: C901
    """Create and register services for the ISY integration."""
    existing_services = hass.services.async_services().get(DOMAIN)
    if existing_services and SERVICE_SEND_PROGRAM_COMMAND in existing_services:
        # Integration-level services have already been added. Return.
        return

    async def async_send_program_command_service_handler(service: ServiceCall) -> None:
        """Handle a send program command service call."""
        address = service.data.get(CONF_ADDRESS)
        name = service.data.get(CONF_NAME)
        command = service.data[CONF_COMMAND]
        isy_name = service.data.get(CONF_ISY)

        for config_entry_id in hass.data[DOMAIN]:
            isy_data = hass.data[DOMAIN][config_entry_id]
            isy = isy_data.root
            if isy_name and isy_name != isy.conf["name"]:
                continue
            program = None
            if address:
                program = isy.programs.get_by_id(address)
            if name:
                program = isy.programs.get_by_name(name)
            if program is not None:
                await getattr(program, command)()
                return
        _LOGGER.error("Could not send program command; not found or enabled on the ISY")

    hass.services.async_register(
        domain=DOMAIN,
        service=SERVICE_SEND_PROGRAM_COMMAND,
        service_func=async_send_program_command_service_handler,
        schema=SERVICE_SEND_PROGRAM_COMMAND_SCHEMA,
    )

    async def _async_send_raw_node_command(call: ServiceCall) -> None:
        await entity_service_call(
            hass, async_get_platforms(hass, DOMAIN), "async_send_raw_node_command", call
        )

    hass.services.async_register(
        domain=DOMAIN,
        service=SERVICE_SEND_RAW_NODE_COMMAND,
        schema=cv.make_entity_service_schema(SERVICE_SEND_RAW_NODE_COMMAND_SCHEMA),
        service_func=_async_send_raw_node_command,
    )

    async def _async_send_node_command(call: ServiceCall) -> None:
        await entity_service_call(
            hass, async_get_platforms(hass, DOMAIN), "async_send_node_command", call
        )

    hass.services.async_register(
        domain=DOMAIN,
        service=SERVICE_SEND_NODE_COMMAND,
        schema=cv.make_entity_service_schema(SERVICE_SEND_NODE_COMMAND_SCHEMA),
        service_func=_async_send_node_command,
    )

    async def _async_get_zwave_parameter(call: ServiceCall) -> None:
        await entity_service_call(
            hass, async_get_platforms(hass, DOMAIN), "async_get_zwave_parameter", call
        )

    hass.services.async_register(
        domain=DOMAIN,
        service=SERVICE_GET_ZWAVE_PARAMETER,
        schema=cv.make_entity_service_schema(SERVICE_GET_ZWAVE_PARAMETER_SCHEMA),
        service_func=_async_get_zwave_parameter,
    )

    async def _async_set_zwave_parameter(call: ServiceCall) -> None:
        await entity_service_call(
            hass, async_get_platforms(hass, DOMAIN), "async_set_zwave_parameter", call
        )

    hass.services.async_register(
        domain=DOMAIN,
        service=SERVICE_SET_ZWAVE_PARAMETER,
        schema=cv.make_entity_service_schema(SERVICE_SET_ZWAVE_PARAMETER_SCHEMA),
        service_func=_async_set_zwave_parameter,
    )

    async def _async_rename_node(call: ServiceCall) -> None:
        await entity_service_call(
            hass, async_get_platforms(hass, DOMAIN), "async_rename_node", call
        )

    hass.services.async_register(
        domain=DOMAIN,
        service=SERVICE_RENAME_NODE,
        schema=cv.make_entity_service_schema(SERVICE_RENAME_NODE_SCHEMA),
        service_func=_async_rename_node,
    )


@callback
def async_unload_services(hass: HomeAssistant) -> None:
    """Unload services for the ISY integration."""
    if hass.data[DOMAIN]:
        # There is still another config entry for this domain, don't remove services.
        return

    existing_services = hass.services.async_services().get(DOMAIN)
    if not existing_services or SERVICE_SEND_PROGRAM_COMMAND not in existing_services:
        return

    _LOGGER.info("Unloading ISY994 Services")
    hass.services.async_remove(domain=DOMAIN, service=SERVICE_SEND_PROGRAM_COMMAND)
    hass.services.async_remove(domain=DOMAIN, service=SERVICE_SEND_RAW_NODE_COMMAND)
    hass.services.async_remove(domain=DOMAIN, service=SERVICE_SEND_NODE_COMMAND)
    hass.services.async_remove(domain=DOMAIN, service=SERVICE_GET_ZWAVE_PARAMETER)
    hass.services.async_remove(domain=DOMAIN, service=SERVICE_SET_ZWAVE_PARAMETER)
