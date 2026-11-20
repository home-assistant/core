"""ISY Services and Commands."""

from enum import StrEnum
from typing import Any

import probatio
from pyisy.constants import COMMAND_FRIENDLY_NAME

from homeassistant.components.lock import DOMAIN as LOCK_DOMAIN
from homeassistant.core import HomeAssistant, ServiceCall, callback
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.entity_platform import async_get_platforms
from homeassistant.helpers.service import (
    async_register_platform_entity_service,
    entity_service_call,
)
from homeassistant.helpers.typing import VolDictType

from .const import DOMAIN, LOGGER
from .models import IsyConfigEntry


class ISYService(StrEnum):
    """Store keys for Universal Devices ISY/IoX services."""

    SEND_RAW_NODE_COMMAND = "send_raw_node_command"
    SEND_NODE_COMMAND = "send_node_command"
    GET_ZWAVE_PARAMETER = "get_zwave_parameter"
    SET_ZWAVE_PARAMETER = "set_zwave_parameter"
    SET_ZWAVE_LOCK_USER_CODE = "set_zwave_lock_user_code"
    DELETE_ZWAVE_LOCK_USER_CODE = "delete_zwave_lock_user_code"
    RENAME_NODE = "rename_node"
    SEND_PROGRAM_COMMAND = "send_program_command"


class ISYServiceArgument(StrEnum):
    """Store keys for Universal Devices ISY/IoX service arguments."""

    COMMAND = "command"
    VALUE = "value"
    PARAMETERS = "parameters"
    UNIT_OF_MEASUREMENT = "unit_of_measurement"
    PARAMETER = "parameter"
    SIZE = "size"
    USER_NUM = "user_num"
    CODE = "code"
    NAME = "name"
    ADDRESS = "address"
    ISY = "isy"


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
    raise probatio.Invalid("Invalid ISY Command.")


SCHEMA_GROUP = "name-address"

SERVICE_SEND_RAW_NODE_COMMAND_SCHEMA = {
    probatio.Required(ISYServiceArgument.COMMAND): probatio.All(
        cv.string, valid_isy_commands
    ),
    probatio.Optional(ISYServiceArgument.VALUE): probatio.All(
        probatio.Coerce(int), probatio.Range(0, 255)
    ),
    probatio.Optional(ISYServiceArgument.UNIT_OF_MEASUREMENT): probatio.All(
        probatio.Coerce(int), probatio.Range(0, 120)
    ),
    probatio.Optional(ISYServiceArgument.PARAMETERS, default={}): {
        cv.string: cv.string
    },
}

SERVICE_SEND_NODE_COMMAND_SCHEMA = {
    probatio.Required(ISYServiceArgument.COMMAND): probatio.In(VALID_NODE_COMMANDS)
}

SERVICE_RENAME_NODE_SCHEMA = {probatio.Required(ISYServiceArgument.NAME): cv.string}

SERVICE_GET_ZWAVE_PARAMETER_SCHEMA = {
    probatio.Required(ISYServiceArgument.PARAMETER): probatio.Coerce(int)
}

SERVICE_SET_ZWAVE_PARAMETER_SCHEMA = {
    probatio.Required(ISYServiceArgument.PARAMETER): probatio.Coerce(int),
    probatio.Required(ISYServiceArgument.VALUE): probatio.Coerce(int),
    probatio.Required(ISYServiceArgument.SIZE): probatio.All(
        probatio.Coerce(int), probatio.In(VALID_PARAMETER_SIZES)
    ),
}

SERVICE_SET_USER_CODE_SCHEMA: VolDictType = {
    probatio.Required(ISYServiceArgument.USER_NUM): probatio.Coerce(int),
    probatio.Required(ISYServiceArgument.CODE): probatio.Coerce(int),
}

SERVICE_DELETE_USER_CODE_SCHEMA: VolDictType = {
    probatio.Required(ISYServiceArgument.USER_NUM): probatio.Coerce(int)
}

SERVICE_SEND_PROGRAM_COMMAND_SCHEMA = probatio.All(
    probatio.AtLeastOne(ISYServiceArgument.ADDRESS, ISYServiceArgument.NAME),
    probatio.Schema(
        {
            probatio.Exclusive(ISYServiceArgument.NAME, SCHEMA_GROUP): cv.string,
            probatio.Exclusive(ISYServiceArgument.ADDRESS, SCHEMA_GROUP): cv.string,
            probatio.Required(ISYServiceArgument.COMMAND): probatio.In(
                VALID_PROGRAM_COMMANDS
            ),
            probatio.Optional(ISYServiceArgument.ISY): cv.string,
        }
    ),
)


def async_get_entities(hass: HomeAssistant) -> dict[str, Entity]:
    """Get entities for a domain."""
    entities: dict[str, Entity] = {}
    for platform in async_get_platforms(hass, DOMAIN):
        entities.update(platform.entities)
    return entities


@callback
def async_setup_services(hass: HomeAssistant) -> None:
    """Create and register services for the ISY integration."""

    async def async_send_program_command_service_handler(service: ServiceCall) -> None:
        """Handle a send program command service call."""
        address = service.data.get(ISYServiceArgument.ADDRESS)
        name = service.data.get(ISYServiceArgument.NAME)
        command = service.data[ISYServiceArgument.COMMAND]
        isy_name = service.data.get(ISYServiceArgument.ISY)

        config_entry: IsyConfigEntry
        for config_entry in hass.config_entries.async_loaded_entries(DOMAIN):
            isy = config_entry.runtime_data.root
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
        LOGGER.error("Could not send program command; not found or enabled on the ISY")

    hass.services.async_register(
        domain=DOMAIN,
        service=ISYService.SEND_PROGRAM_COMMAND,
        service_func=async_send_program_command_service_handler,
        schema=SERVICE_SEND_PROGRAM_COMMAND_SCHEMA,
    )

    async def _async_send_raw_node_command(call: ServiceCall) -> None:
        await entity_service_call(
            hass, async_get_entities(hass), "async_send_raw_node_command", call
        )

    hass.services.async_register(
        domain=DOMAIN,
        service=ISYService.SEND_RAW_NODE_COMMAND,
        schema=cv.make_entity_service_schema(SERVICE_SEND_RAW_NODE_COMMAND_SCHEMA),
        service_func=_async_send_raw_node_command,
    )

    async def _async_send_node_command(call: ServiceCall) -> None:
        await entity_service_call(
            hass, async_get_entities(hass), "async_send_node_command", call
        )

    hass.services.async_register(
        domain=DOMAIN,
        service=ISYService.SEND_NODE_COMMAND,
        schema=cv.make_entity_service_schema(SERVICE_SEND_NODE_COMMAND_SCHEMA),
        service_func=_async_send_node_command,
    )

    async def _async_get_zwave_parameter(call: ServiceCall) -> None:
        await entity_service_call(
            hass, async_get_entities(hass), "async_get_zwave_parameter", call
        )

    hass.services.async_register(
        domain=DOMAIN,
        service=ISYService.GET_ZWAVE_PARAMETER,
        schema=cv.make_entity_service_schema(SERVICE_GET_ZWAVE_PARAMETER_SCHEMA),
        service_func=_async_get_zwave_parameter,
    )

    async def _async_set_zwave_parameter(call: ServiceCall) -> None:
        await entity_service_call(
            hass, async_get_entities(hass), "async_set_zwave_parameter", call
        )

    hass.services.async_register(
        domain=DOMAIN,
        service=ISYService.SET_ZWAVE_PARAMETER,
        schema=cv.make_entity_service_schema(SERVICE_SET_ZWAVE_PARAMETER_SCHEMA),
        service_func=_async_set_zwave_parameter,
    )

    async def _async_rename_node(call: ServiceCall) -> None:
        await entity_service_call(
            hass, async_get_entities(hass), "async_rename_node", call
        )

    hass.services.async_register(
        domain=DOMAIN,
        service=ISYService.RENAME_NODE,
        schema=cv.make_entity_service_schema(SERVICE_RENAME_NODE_SCHEMA),
        service_func=_async_rename_node,
    )

    async_register_platform_entity_service(
        hass,
        DOMAIN,
        ISYService.SET_ZWAVE_LOCK_USER_CODE,
        entity_domain=LOCK_DOMAIN,
        func="async_set_zwave_lock_user_code",
        schema=SERVICE_SET_USER_CODE_SCHEMA,
    )
    async_register_platform_entity_service(
        hass,
        DOMAIN,
        ISYService.DELETE_ZWAVE_LOCK_USER_CODE,
        entity_domain=LOCK_DOMAIN,
        func="async_delete_zwave_lock_user_code",
        schema=SERVICE_DELETE_USER_CODE_SCHEMA,
    )
