"""ISY Services and Commands."""
from __future__ import annotations

from typing import Any

from pyisy.constants import COMMAND_FRIENDLY_NAME
import voluptuous as vol

from homeassistant.const import (
    CONF_ADDRESS,
    CONF_COMMAND,
    CONF_NAME,
    CONF_TYPE,
    CONF_UNIT_OF_MEASUREMENT,
    SERVICE_RELOAD,
    Platform,
)
from homeassistant.core import HomeAssistant, ServiceCall, callback
from homeassistant.helpers import entity_platform
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.entity_platform import async_get_platforms
import homeassistant.helpers.entity_registry as er
from homeassistant.helpers.issue_registry import IssueSeverity, async_create_issue
from homeassistant.helpers.service import entity_service_call

from .const import _LOGGER, CONF_NETWORK, DOMAIN, ISY_CONF_NAME
from .util import _async_cleanup_registry_entries

# Common Services for All Platforms:
SERVICE_SYSTEM_QUERY = "system_query"
SERVICE_SET_VARIABLE = "set_variable"
SERVICE_SEND_PROGRAM_COMMAND = "send_program_command"
SERVICE_RUN_NETWORK_RESOURCE = "run_network_resource"
SERVICE_CLEANUP = "cleanup_entities"

INTEGRATION_SERVICES = [
    SERVICE_SYSTEM_QUERY,
    SERVICE_SET_VARIABLE,
    SERVICE_SEND_PROGRAM_COMMAND,
    SERVICE_RUN_NETWORK_RESOURCE,
    SERVICE_CLEANUP,
]

# Entity specific methods (valid for most Groups/ISY Scenes, Lights, Switches, Fans)
SERVICE_SEND_RAW_NODE_COMMAND = "send_raw_node_command"
SERVICE_SEND_NODE_COMMAND = "send_node_command"
SERVICE_GET_ZWAVE_PARAMETER = "get_zwave_parameter"
SERVICE_SET_ZWAVE_PARAMETER = "set_zwave_parameter"
SERVICE_RENAME_NODE = "rename_node"

# Services valid only for dimmable lights.
SERVICE_SET_ON_LEVEL = "set_on_level"
SERVICE_SET_RAMP_RATE = "set_ramp_rate"

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

SERVICE_SYSTEM_QUERY_SCHEMA = vol.Schema(
    {vol.Optional(CONF_ADDRESS): cv.string, vol.Optional(CONF_ISY): cv.string}
)

SERVICE_SET_RAMP_RATE_SCHEMA = {
    vol.Required(CONF_VALUE): vol.All(vol.Coerce(int), vol.Range(0, 31))
}

SERVICE_SET_VALUE_SCHEMA = {
    vol.Required(CONF_VALUE): vol.All(vol.Coerce(int), vol.Range(0, 255))
}

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

SERVICE_SET_VARIABLE_SCHEMA = vol.All(
    cv.has_at_least_one_key(CONF_ADDRESS, CONF_TYPE, CONF_NAME),
    vol.Schema(
        {
            vol.Exclusive(CONF_NAME, SCHEMA_GROUP): cv.string,
            vol.Inclusive(CONF_ADDRESS, SCHEMA_GROUP): vol.Coerce(int),
            vol.Inclusive(CONF_TYPE, SCHEMA_GROUP): vol.All(
                vol.Coerce(int), vol.Range(1, 2)
            ),
            vol.Optional(CONF_INIT, default=False): bool,
            vol.Required(CONF_VALUE): vol.Coerce(int),
            vol.Optional(CONF_ISY): cv.string,
        }
    ),
)

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

SERVICE_RUN_NETWORK_RESOURCE_SCHEMA = vol.All(
    cv.has_at_least_one_key(CONF_ADDRESS, CONF_NAME),
    vol.Schema(
        {
            vol.Exclusive(CONF_NAME, SCHEMA_GROUP): cv.string,
            vol.Exclusive(CONF_ADDRESS, SCHEMA_GROUP): vol.Coerce(int),
            vol.Optional(CONF_ISY): cv.string,
        }
    ),
)


@callback
def async_setup_services(hass: HomeAssistant) -> None:  # noqa: C901
    """Create and register services for the ISY integration."""
    existing_services = hass.services.async_services().get(DOMAIN)
    if existing_services and any(
        service in INTEGRATION_SERVICES for service in existing_services
    ):
        # Integration-level services have already been added. Return.
        return

    async def async_system_query_service_handler(service: ServiceCall) -> None:
        """Handle a system query service call."""
        address = service.data.get(CONF_ADDRESS)
        isy_name = service.data.get(CONF_ISY)
        entity_registry = er.async_get(hass)
        for config_entry_id in hass.data[DOMAIN]:
            isy_data = hass.data[DOMAIN][config_entry_id]
            isy = isy_data.root
            if isy_name and isy_name != isy.conf["name"]:
                continue
            # If an address is provided, make sure we query the correct ISY.
            # Otherwise, query the whole system on all ISY's connected.
            if address and isy.nodes.get_by_id(address) is not None:
                _LOGGER.debug(
                    "Requesting query of device %s on ISY %s",
                    address,
                    isy.uuid,
                )
                await isy.query(address)
                async_log_deprecated_service_call(
                    hass,
                    call=service,
                    alternate_service="button.press",
                    alternate_target=entity_registry.async_get_entity_id(
                        Platform.BUTTON,
                        DOMAIN,
                        f"{isy.uuid}_{address}_query",
                    ),
                    breaks_in_ha_version="2023.5.0",
                )
                return
            _LOGGER.debug("Requesting system query of ISY %s", isy.uuid)
            await isy.query()
            async_log_deprecated_service_call(
                hass,
                call=service,
                alternate_service="button.press",
                alternate_target=entity_registry.async_get_entity_id(
                    Platform.BUTTON, DOMAIN, f"{isy.uuid}_query"
                ),
                breaks_in_ha_version="2023.5.0",
            )

    async def async_run_network_resource_service_handler(service: ServiceCall) -> None:
        """Handle a network resource service call."""
        address = service.data.get(CONF_ADDRESS)
        name = service.data.get(CONF_NAME)
        isy_name = service.data.get(CONF_ISY)

        for config_entry_id in hass.data[DOMAIN]:
            isy_data = hass.data[DOMAIN][config_entry_id]
            isy = isy_data.root
            if isy_name and isy_name != isy.conf[ISY_CONF_NAME]:
                continue
            if isy.networking is None:
                continue
            command = None
            if address:
                command = isy.networking.get_by_id(address)
            if name:
                command = isy.networking.get_by_name(name)
            if command is not None:
                await command.run()
                entity_registry = er.async_get(hass)
                async_log_deprecated_service_call(
                    hass,
                    call=service,
                    alternate_service="button.press",
                    alternate_target=entity_registry.async_get_entity_id(
                        Platform.BUTTON,
                        DOMAIN,
                        f"{isy.uuid}_{CONF_NETWORK}_{address}",
                    ),
                    breaks_in_ha_version="2023.5.0",
                )
                return
        _LOGGER.error(
            "Could not run network resource command; not found or enabled on the ISY"
        )

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

    async def async_set_variable_service_handler(service: ServiceCall) -> None:
        """Handle a set variable service call."""
        address = service.data.get(CONF_ADDRESS)
        vtype = service.data.get(CONF_TYPE)
        name = service.data.get(CONF_NAME)
        value = service.data.get(CONF_VALUE)
        init = service.data.get(CONF_INIT, False)
        isy_name = service.data.get(CONF_ISY)

        for config_entry_id in hass.data[DOMAIN]:
            isy_data = hass.data[DOMAIN][config_entry_id]
            isy = isy_data.root
            if isy_name and isy_name != isy.conf["name"]:
                continue
            variable = None
            if name:
                variable = isy.variables.get_by_name(name)
            if address and vtype:
                variable = isy.variables.vobjs[vtype].get(address)
            if variable is not None:
                await variable.set_value(value, init)
                entity_registry = er.async_get(hass)
                async_log_deprecated_service_call(
                    hass,
                    call=service,
                    alternate_service="number.set_value",
                    alternate_target=entity_registry.async_get_entity_id(
                        Platform.NUMBER,
                        DOMAIN,
                        f"{isy.uuid}_{address}{'_init' if init else ''}",
                    ),
                    breaks_in_ha_version="2023.5.0",
                )
                return
        _LOGGER.error("Could not set variable value; not found or enabled on the ISY")

    @callback
    def async_cleanup_registry_entries(service: ServiceCall) -> None:
        """Remove extra entities that are no longer part of the integration."""
        async_log_deprecated_service_call(
            hass,
            call=service,
            alternate_service="homeassistant.reload_core_config",
            alternate_target=None,
            breaks_in_ha_version="2023.5.0",
        )
        for config_entry_id in hass.data[DOMAIN]:
            _async_cleanup_registry_entries(hass, config_entry_id)

    async def async_reload_config_entries(service: ServiceCall) -> None:
        """Trigger a reload of all ISY config entries."""
        async_log_deprecated_service_call(
            hass,
            call=service,
            alternate_service="homeassistant.reload_core_config",
            alternate_target=None,
            breaks_in_ha_version="2023.5.0",
        )
        for config_entry_id in hass.data[DOMAIN]:
            hass.async_create_task(hass.config_entries.async_reload(config_entry_id))

    hass.services.async_register(
        domain=DOMAIN,
        service=SERVICE_SYSTEM_QUERY,
        service_func=async_system_query_service_handler,
        schema=SERVICE_SYSTEM_QUERY_SCHEMA,
    )

    hass.services.async_register(
        domain=DOMAIN,
        service=SERVICE_RUN_NETWORK_RESOURCE,
        service_func=async_run_network_resource_service_handler,
        schema=SERVICE_RUN_NETWORK_RESOURCE_SCHEMA,
    )

    hass.services.async_register(
        domain=DOMAIN,
        service=SERVICE_SEND_PROGRAM_COMMAND,
        service_func=async_send_program_command_service_handler,
        schema=SERVICE_SEND_PROGRAM_COMMAND_SCHEMA,
    )

    hass.services.async_register(
        domain=DOMAIN,
        service=SERVICE_SET_VARIABLE,
        service_func=async_set_variable_service_handler,
        schema=SERVICE_SET_VARIABLE_SCHEMA,
    )

    hass.services.async_register(
        domain=DOMAIN,
        service=SERVICE_CLEANUP,
        service_func=async_cleanup_registry_entries,
    )

    hass.services.async_register(
        domain=DOMAIN, service=SERVICE_RELOAD, service_func=async_reload_config_entries
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
    if not existing_services or not any(
        service in INTEGRATION_SERVICES for service in existing_services
    ):
        return

    _LOGGER.info("Unloading ISY994 Services")
    hass.services.async_remove(domain=DOMAIN, service=SERVICE_SYSTEM_QUERY)
    hass.services.async_remove(domain=DOMAIN, service=SERVICE_RUN_NETWORK_RESOURCE)
    hass.services.async_remove(domain=DOMAIN, service=SERVICE_SEND_PROGRAM_COMMAND)
    hass.services.async_remove(domain=DOMAIN, service=SERVICE_SET_VARIABLE)
    hass.services.async_remove(domain=DOMAIN, service=SERVICE_CLEANUP)
    hass.services.async_remove(domain=DOMAIN, service=SERVICE_RELOAD)
    hass.services.async_remove(domain=DOMAIN, service=SERVICE_SEND_RAW_NODE_COMMAND)
    hass.services.async_remove(domain=DOMAIN, service=SERVICE_SEND_NODE_COMMAND)


@callback
def async_setup_light_services(hass: HomeAssistant) -> None:
    """Create device-specific services for the ISY Integration."""
    platform = entity_platform.async_get_current_platform()

    platform.async_register_entity_service(
        SERVICE_SET_ON_LEVEL, SERVICE_SET_VALUE_SCHEMA, "async_set_on_level"
    )
    platform.async_register_entity_service(
        SERVICE_SET_RAMP_RATE, SERVICE_SET_RAMP_RATE_SCHEMA, "async_set_ramp_rate"
    )


@callback
def async_log_deprecated_service_call(
    hass: HomeAssistant,
    call: ServiceCall,
    alternate_service: str,
    alternate_target: str | None,
    breaks_in_ha_version: str,
) -> None:
    """Log a warning about a deprecated service call."""
    deprecated_service = f"{call.domain}.{call.service}"
    alternate_target = alternate_target or "this device"

    async_create_issue(
        hass,
        DOMAIN,
        f"deprecated_service_{deprecated_service}",
        breaks_in_ha_version=breaks_in_ha_version,
        is_fixable=True,
        is_persistent=True,
        severity=IssueSeverity.WARNING,
        translation_key="deprecated_service",
        translation_placeholders={
            "alternate_service": alternate_service,
            "alternate_target": alternate_target,
            "deprecated_service": deprecated_service,
        },
    )

    alternate_text = ""
    if alternate_target:
        alternate_text = f' and pass it a target entity ID of "{alternate_target}"'

    _LOGGER.warning(
        (
            'The "%s" service is deprecated and will be removed in %s; use the "%s" '
            "service %s"
        ),
        deprecated_service,
        breaks_in_ha_version,
        alternate_service,
        alternate_text,
    )
