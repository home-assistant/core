"""Support for Modbus services."""

from collections.abc import Callable
from typing import Any

import voluptuous as vol

from homeassistant.const import ATTR_STATE, SERVICE_RELOAD
from homeassistant.core import HomeAssistant, ServiceCall, callback
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.dispatcher import async_dispatcher_send
from homeassistant.helpers.entity_platform import async_get_platforms
from homeassistant.helpers.reload import async_integration_yaml_config
from homeassistant.helpers.service import async_register_admin_service

from .const import (
    ATTR_ADDRESS,
    ATTR_HUB,
    ATTR_SLAVE,
    ATTR_UNIT,
    ATTR_VALUE,
    CALL_TYPE_WRITE_COIL,
    CALL_TYPE_WRITE_COILS,
    CALL_TYPE_WRITE_REGISTER,
    CALL_TYPE_WRITE_REGISTERS,
    DATA_MODBUS_HUBS,
    DEFAULT_HUB,
    DOMAIN,
    LOGGER,
    SERVICE_STOP,
    SERVICE_WRITE_COIL,
    SERVICE_WRITE_REGISTER,
    SIGNAL_STOP_ENTITY,
)
from .modbus import ModbusHub, async_modbus_setup


def _write_service_schema(attr: str, validator: Callable[[Any], Any]) -> vol.Schema:
    """Return the schema shared by the write actions."""
    return vol.Schema(
        {
            vol.Optional(ATTR_HUB, default=DEFAULT_HUB): cv.string,
            vol.Exclusive(ATTR_SLAVE, "unit"): cv.positive_int,
            vol.Exclusive(ATTR_UNIT, "unit"): cv.positive_int,
            vol.Required(ATTR_ADDRESS): cv.positive_int,
            vol.Required(attr): vol.Any(
                cv.positive_int, vol.All(cv.ensure_list, [validator])
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
    device_address = service.data.get(ATTR_SLAVE, service.data.get(ATTR_UNIT, 1))
    address = service.data[ATTR_ADDRESS]
    hub = _get_hubs(service.hass)[service.data[ATTR_HUB]]
    return (hub, device_address, address)


async def _async_write_register(service: ServiceCall) -> None:
    """Write Modbus registers."""
    hub, device_address, address = _get_service_call_details(service)

    value = service.data[ATTR_VALUE]
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

    state = service.data[ATTR_STATE]

    if isinstance(state, list):
        await hub.async_pb_call(device_address, address, state, CALL_TYPE_WRITE_COILS)
    else:
        await hub.async_pb_call(device_address, address, state, CALL_TYPE_WRITE_COIL)


async def _async_stop_hub(service: ServiceCall) -> None:
    """Stop Modbus hub."""
    hass = service.hass
    hub = _get_hubs(hass)[service.data[ATTR_HUB]]
    async_dispatcher_send(hass, SIGNAL_STOP_ENTITY.format(hub.name))
    await hub.async_close()


async def _async_reload_config(call: ServiceCall) -> None:
    """Reload Modbus."""
    hass = call.hass
    if DATA_MODBUS_HUBS not in hass.data:
        LOGGER.error("Modbus cannot reload, because it was never loaded")
        return
    hubs = hass.data[DATA_MODBUS_HUBS]
    for hub in hubs.values():
        await hub.async_close()
    reset_platforms = async_get_platforms(hass, DOMAIN)
    for reset_platform in reset_platforms:
        LOGGER.debug("Reload modbus resetting platform: %s", reset_platform.domain)
        await reset_platform.async_reset()
    reload_config = await async_integration_yaml_config(hass, DOMAIN)
    if not reload_config:
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
    async_register_admin_service(hass, DOMAIN, SERVICE_RELOAD, _async_reload_config)
    hass.services.async_register(
        DOMAIN,
        SERVICE_WRITE_REGISTER,
        _async_write_register,
        schema=_write_service_schema(ATTR_VALUE, cv.positive_int),
    )
    hass.services.async_register(
        DOMAIN,
        SERVICE_WRITE_COIL,
        _async_write_coil,
        schema=_write_service_schema(ATTR_STATE, cv.boolean),
    )
    hass.services.async_register(
        DOMAIN,
        SERVICE_STOP,
        _async_stop_hub,
        schema=vol.Schema({vol.Required(ATTR_HUB): cv.string}),
    )
