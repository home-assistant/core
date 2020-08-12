"""ISY Services and Commands."""

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
)
from homeassistant.core import callback
from homeassistant.helpers import entity_platform
import homeassistant.helpers.config_validation as cv
import homeassistant.helpers.entity_registry as er
from homeassistant.helpers.typing import HomeAssistantType

from .const import (
    _LOGGER,
    DOMAIN,
    ISY994_ISY,
    ISY994_NODES,
    ISY994_PROGRAMS,
    ISY994_VARIABLES,
    SUPPORTED_PLATFORMS,
    SUPPORTED_PROGRAM_PLATFORMS,
)

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

# Services valid only for dimmable lights.
SERVICE_SET_ON_LEVEL = "set_on_level"
SERVICE_SET_RAMP_RATE = "set_ramp_rate"

CONF_PARAMETERS = "parameters"
CONF_VALUE = "value"
CONF_INIT = "init"
CONF_ISY = "isy"

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


def valid_isy_commands(value: Any) -> str:
    """Validate the command is valid."""
    value = str(value).upper()
    if value in COMMAND_FRIENDLY_NAME.keys():
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
def async_setup_services(hass: HomeAssistantType):
    """Create and register services for the ISY integration."""
    existing_services = hass.services.async_services().get(DOMAIN)
    if existing_services and any(
        service in INTEGRATION_SERVICES for service in existing_services.keys()
    ):
        # Integration-level services have already been added. Return.
        return

    async def async_system_query_service_handler(service):
        """Handle a system query service call."""
        address = service.data.get(CONF_ADDRESS)
        isy_name = service.data.get(CONF_ISY)

        for config_entry_id in hass.data[DOMAIN]:
            isy = hass.data[DOMAIN][config_entry_id][ISY994_ISY]
            if isy_name and not isy_name == isy.configuration["name"]:
                continue
            # If an address is provided, make sure we query the correct ISY.
            # Otherwise, query the whole system on all ISY's connected.
            if address and isy.nodes.get_by_id(address) is not None:
                _LOGGER.debug(
                    "Requesting query of device %s on ISY %s",
                    address,
                    isy.configuration["uuid"],
                )
                await hass.async_add_executor_job(isy.query, address)
                return
            _LOGGER.debug(
                "Requesting system query of ISY %s", isy.configuration["uuid"]
            )
            await hass.async_add_executor_job(isy.query)

    async def async_run_network_resource_service_handler(service):
        """Handle a network resource service call."""
        address = service.data.get(CONF_ADDRESS)
        name = service.data.get(CONF_NAME)
        isy_name = service.data.get(CONF_ISY)

        for config_entry_id in hass.data[DOMAIN]:
            isy = hass.data[DOMAIN][config_entry_id][ISY994_ISY]
            if isy_name and not isy_name == isy.configuration["name"]:
                continue
            if not hasattr(isy, "networking") or isy.networking is None:
                continue
            command = None
            if address:
                command = isy.networking.get_by_id(address)
            if name:
                command = isy.networking.get_by_name(name)
            if command is not None:
                await hass.async_add_executor_job(command.run)
                return
        _LOGGER.error(
            "Could not run network resource command. Not found or enabled on the ISY"
        )

    async def async_send_program_command_service_handler(service):
        """Handle a send program command service call."""
        address = service.data.get(CONF_ADDRESS)
        name = service.data.get(CONF_NAME)
        command = service.data.get(CONF_COMMAND)
        isy_name = service.data.get(CONF_ISY)

        for config_entry_id in hass.data[DOMAIN]:
            isy = hass.data[DOMAIN][config_entry_id][ISY994_ISY]
            if isy_name and not isy_name == isy.configuration["name"]:
                continue
            program = None
            if address:
                program = isy.programs.get_by_id(address)
            if name:
                program = isy.programs.get_by_name(name)
            if program is not None:
                await hass.async_add_executor_job(getattr(program, command))
                return
        _LOGGER.error("Could not send program command. Not found or enabled on the ISY")

    async def async_set_variable_service_handler(service):
        """Handle a set variable service call."""
        address = service.data.get(CONF_ADDRESS)
        vtype = service.data.get(CONF_TYPE)
        name = service.data.get(CONF_NAME)
        value = service.data.get(CONF_VALUE)
        init = service.data.get(CONF_INIT, False)
        isy_name = service.data.get(CONF_ISY)

        for config_entry_id in hass.data[DOMAIN]:
            isy = hass.data[DOMAIN][config_entry_id][ISY994_ISY]
            if isy_name and not isy_name == isy.configuration["name"]:
                continue
            variable = None
            if name:
                variable = isy.variables.get_by_name(name)
            if address and vtype:
                variable = isy.variables.vobjs[vtype].get(address)
            if variable is not None:
                await hass.async_add_executor_job(variable.set_value, value, init)
                return
        _LOGGER.error("Could not set variable value. Not found or enabled on the ISY")

    async def async_cleanup_registry_entries(service) -> None:
        """Remove extra entities that are no longer part of the integration."""
        entity_registry = await er.async_get_registry(hass)
        config_ids = []
        current_unique_ids = []

        for config_entry_id in hass.data[DOMAIN]:
            entries_for_this_config = er.async_entries_for_config_entry(
                entity_registry, config_entry_id
            )
            config_ids.extend(
                [
                    (entity.unique_id, entity.entity_id)
                    for entity in entries_for_this_config
                ]
            )

            hass_isy_data = hass.data[DOMAIN][config_entry_id]
            uuid = hass_isy_data[ISY994_ISY].configuration["uuid"]

            for platform in SUPPORTED_PLATFORMS:
                for node in hass_isy_data[ISY994_NODES][platform]:
                    if hasattr(node, "address"):
                        current_unique_ids.append(f"{uuid}_{node.address}")

            for platform in SUPPORTED_PROGRAM_PLATFORMS:
                for _, node, _ in hass_isy_data[ISY994_PROGRAMS][platform]:
                    if hasattr(node, "address"):
                        current_unique_ids.append(f"{uuid}_{node.address}")

            for node in hass_isy_data[ISY994_VARIABLES]:
                if hasattr(node, "address"):
                    current_unique_ids.append(f"{uuid}_{node.address}")

        extra_entities = [
            entity_id
            for unique_id, entity_id in config_ids
            if unique_id not in current_unique_ids
        ]

        for entity_id in extra_entities:
            if entity_registry.async_is_registered(entity_id):
                entity_registry.async_remove(entity_id)

        _LOGGER.debug(
            "Cleaning up ISY994 Entities and devices: Config Entries: %s, Current Entries: %s, "
            "Extra Entries Removed: %s",
            len(config_ids),
            len(current_unique_ids),
            len(extra_entities),
        )

    async def async_reload_config_entries(service) -> None:
        """Trigger a reload of all ISY994 config entries."""
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


@callback
def async_unload_services(hass: HomeAssistantType):
    """Unload services for the ISY integration."""
    if hass.data[DOMAIN]:
        # There is still another config entry for this domain, don't remove services.
        return

    existing_services = hass.services.async_services().get(DOMAIN)
    if not existing_services or not any(
        service in INTEGRATION_SERVICES for service in existing_services.keys()
    ):
        return

    _LOGGER.info("Unloading ISY994 Services")
    hass.services.async_remove(domain=DOMAIN, service=SERVICE_SYSTEM_QUERY)
    hass.services.async_remove(domain=DOMAIN, service=SERVICE_RUN_NETWORK_RESOURCE)
    hass.services.async_remove(domain=DOMAIN, service=SERVICE_SEND_PROGRAM_COMMAND)
    hass.services.async_remove(domain=DOMAIN, service=SERVICE_SET_VARIABLE)
    hass.services.async_remove(domain=DOMAIN, service=SERVICE_CLEANUP)
    hass.services.async_remove(domain=DOMAIN, service=SERVICE_RELOAD)


@callback
def async_setup_device_services(hass: HomeAssistantType):
    """Create device-specific services for the ISY Integration."""
    platform = entity_platform.current_platform.get()

    platform.async_register_entity_service(
        SERVICE_SEND_RAW_NODE_COMMAND,
        SERVICE_SEND_RAW_NODE_COMMAND_SCHEMA,
        SERVICE_SEND_RAW_NODE_COMMAND,
    )
    platform.async_register_entity_service(
        SERVICE_SEND_NODE_COMMAND,
        SERVICE_SEND_NODE_COMMAND_SCHEMA,
        SERVICE_SEND_NODE_COMMAND,
    )


@callback
def async_setup_light_services(hass: HomeAssistantType):
    """Create device-specific services for the ISY Integration."""
    platform = entity_platform.current_platform.get()

    platform.async_register_entity_service(
        SERVICE_SET_ON_LEVEL, SERVICE_SET_VALUE_SCHEMA, SERVICE_SET_ON_LEVEL
    )
    platform.async_register_entity_service(
        SERVICE_SET_RAMP_RATE, SERVICE_SET_RAMP_RATE_SCHEMA, SERVICE_SET_RAMP_RATE
    )
