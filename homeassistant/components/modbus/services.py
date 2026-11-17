"""Support for Modbus services."""

from collections.abc import Callable
from enum import StrEnum
from typing import Any

import probatio

from homeassistant.core import HomeAssistant, ServiceCall, callback
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.dispatcher import async_dispatcher_send
from homeassistant.helpers.entity_platform import async_get_platforms
from homeassistant.helpers.reload import async_integration_yaml_config
from homeassistant.helpers.service import async_register_admin_service

from .const import (
    CALL_TYPE_WRITE_COIL,
    CALL_TYPE_WRITE_COILS,
    CALL_TYPE_WRITE_REGISTER,
    CALL_TYPE_WRITE_REGISTERS,
    DATA_MODBUS_HUBS,
    DEFAULT_HUB,
    DOMAIN,
    LOGGER,
    SIGNAL_STOP_ENTITY,
)
from .modbus import ModbusHub, async_modbus_setup


class ModbusService(StrEnum):
    """Store keys for Modbus services."""

    RELOAD = "reload"
    STOP = "stop"
    WRITE_COIL = "write_coil"
    WRITE_REGISTER = "write_register"


class ModbusServiceArgument(StrEnum):
    """Store keys for Modbus service arguments."""

    ADDRESS = "address"
    HUB = "hub"
    SLAVE = "slave"
    STATE = "state"
    UNIT = "unit"
    VALUE = "value"


def _write_service_schema(
    attr: str, validator: Callable[[Any], Any]
) -> probatio.Schema:
    """Return the schema shared by the write actions."""
    return probatio.Schema(
        {
            probatio.Optional(
                ModbusServiceArgument.HUB, default=DEFAULT_HUB
            ): cv.string,
            probatio.Exclusive(ModbusServiceArgument.SLAVE, "unit"): cv.positive_int,
            probatio.Exclusive(ModbusServiceArgument.UNIT, "unit"): cv.positive_int,
            probatio.Required(ModbusServiceArgument.ADDRESS): cv.positive_int,
            probatio.Required(attr): probatio.Any(
                cv.positive_int, probatio.All(probatio.EnsureList(), [validator])
            ),
        }
    )


def _get_hubs(hass: HomeAssistant) -> dict[str, ModbusHub]:
    """Return the configured Modbus hubs, raising if Modbus is not set up."""
    if not (hubs := hass.data.get(DATA_MODBUS_HUBS)):
        raise ServiceValidationError(
            translation_domain=DOMAIN,
            translation_key="not_loaded",
        )

    return hubs


def _get_service_call_details(service: ServiceCall) -> tuple[ModbusHub, int, int]:
    """Return the details required to process the service call."""
    device_address = service.data.get(
        ModbusServiceArgument.SLAVE, service.data.get(ModbusServiceArgument.UNIT, 1)
    )
    address = service.data[ModbusServiceArgument.ADDRESS]
    hub = _get_hubs(service.hass)[service.data[ModbusServiceArgument.HUB]]
    return (hub, device_address, address)


async def _async_write_register(service: ServiceCall) -> None:
    """Write Modbus registers."""
    hub, device_address, address = _get_service_call_details(service)

    value = service.data[ModbusServiceArgument.VALUE]
    if isinstance(value, list):
        await hub.async_pb_call(
            device_address, address, value, CALL_TYPE_WRITE_REGISTERS
        )
    else:
        await hub.async_pb_call(
            device_address, address, value, CALL_TYPE_WRITE_REGISTER
        )


async def _async_write_coil(service: ServiceCall) -> None:
    """Write Modbus coil."""
    hub, device_address, address = _get_service_call_details(service)

    state = service.data[ModbusServiceArgument.STATE]

    if isinstance(state, list):
        await hub.async_pb_call(device_address, address, state, CALL_TYPE_WRITE_COILS)
    else:
        await hub.async_pb_call(device_address, address, state, CALL_TYPE_WRITE_COIL)


async def _async_stop_hub(service: ServiceCall) -> None:
    """Stop Modbus hub."""
    hass = service.hass
    hub = _get_hubs(hass)[service.data[ModbusServiceArgument.HUB]]
    async_dispatcher_send(hass, SIGNAL_STOP_ENTITY.format(hub.name))
    await hub.async_close()


async def _async_reload_config(call: ServiceCall) -> None:
    """Reload Modbus."""
    hass = call.hass
    # A failed setup stays cached, so the platforms would be rejected
    if DOMAIN not in hass.config.components:
        LOGGER.error("Modbus failed to set up, restart Home Assistant to retry")
        return
    # Without YAML hubs there is nothing to close, but YAML may have been added
    hubs = hass.data.get(DATA_MODBUS_HUBS, {})
    for hub in hubs.values():
        await hub.async_close()
    reset_platforms = async_get_platforms(hass, DOMAIN)
    for reset_platform in reset_platforms:
        LOGGER.debug("Reload modbus resetting platform: %s", reset_platform.domain)
        await reset_platform.async_reset()
    reload_config = await async_integration_yaml_config(hass, DOMAIN)
    # The loaded YAML holds every integration's config, not just this one's
    if not reload_config or DOMAIN not in reload_config:
        LOGGER.debug("Modbus not present anymore")
        hubs.clear()
        return
    LOGGER.debug("Modbus reloading")
    # Setup replaces the hubs only once it has new ones to replace them with
    if not await async_modbus_setup(hass, reload_config):
        hubs.clear()


@callback
def async_setup_services(hass: HomeAssistant) -> None:
    """Register the Modbus services."""
    async_register_admin_service(
        hass, DOMAIN, ModbusService.RELOAD, _async_reload_config
    )
    hass.services.async_register(
        DOMAIN,
        ModbusService.WRITE_REGISTER,
        _async_write_register,
        schema=_write_service_schema(ModbusServiceArgument.VALUE, cv.positive_int),
    )
    hass.services.async_register(
        DOMAIN,
        ModbusService.WRITE_COIL,
        _async_write_coil,
        schema=_write_service_schema(ModbusServiceArgument.STATE, cv.boolean),
    )
    hass.services.async_register(
        DOMAIN,
        ModbusService.STOP,
        _async_stop_hub,
        schema=probatio.Schema(
            {probatio.Required(ModbusServiceArgument.HUB): cv.string}
        ),
    )
