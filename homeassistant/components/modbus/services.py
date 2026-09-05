"""Support for Modbus services."""

from typing import TYPE_CHECKING

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
from .modbus import async_modbus_setup

if TYPE_CHECKING:
    from .modbus import ModbusHub


def _get_hubs(hass: HomeAssistant) -> dict[str, ModbusHub]:
    """Return the configured Modbus hubs, raising if Modbus is not set up."""
    if not (hubs := hass.data.get(DATA_MODBUS_HUBS)):
        raise ServiceValidationError(
            translation_domain=DOMAIN,
            translation_key="not_loaded",
        )

    return hubs


def _get_service_call_details(
    service: ServiceCall,
) -> tuple[ModbusHub, int, int]:
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
    async_dispatcher_send(service.hass, SIGNAL_STOP_ENTITY)
    hub = _get_hubs(service.hass)[service.data[ATTR_HUB]]
    await hub.async_close()


async def _async_reload_config(call: ServiceCall) -> None:
    """Reload Modbus."""
    hass = call.hass
    if not hass.data.get(DATA_MODBUS_HUBS):
        LOGGER.error("Modbus cannot reload, because it was never loaded")
        return
    for hub in hass.data[DATA_MODBUS_HUBS].values():
        await hub.async_close()
    reset_platforms = async_get_platforms(hass, DOMAIN)
    for reset_platform in reset_platforms:
        LOGGER.debug("Reload modbus resetting platform: %s", reset_platform.domain)
        await reset_platform.async_reset()
    reload_config = await async_integration_yaml_config(hass, DOMAIN)
    if not reload_config:
        LOGGER.debug("Modbus not present anymore")
        return
    LOGGER.debug("Modbus reloading")
    await async_modbus_setup(hass, reload_config)


@callback
def async_setup_services(hass: HomeAssistant) -> None:
    """Register the Modbus services."""
    for service_name, service_func, attr, validator in (
        (SERVICE_WRITE_REGISTER, _async_write_register, ATTR_VALUE, cv.positive_int),
        (SERVICE_WRITE_COIL, _async_write_coil, ATTR_STATE, cv.boolean),
    ):
        hass.services.async_register(
            DOMAIN,
            service_name,
            service_func,
            schema=vol.Schema(
                {
                    vol.Optional(ATTR_HUB, default=DEFAULT_HUB): cv.string,
                    vol.Exclusive(ATTR_SLAVE, "unit"): cv.positive_int,
                    vol.Exclusive(ATTR_UNIT, "unit"): cv.positive_int,
                    vol.Required(ATTR_ADDRESS): cv.positive_int,
                    vol.Required(attr): vol.Any(
                        cv.positive_int, vol.All(cv.ensure_list, [validator])
                    ),
                }
            ),
        )

    hass.services.async_register(
        DOMAIN,
        SERVICE_STOP,
        _async_stop_hub,
        schema=vol.Schema({vol.Required(ATTR_HUB): cv.string}),
    )

    async_register_admin_service(hass, DOMAIN, SERVICE_RELOAD, _async_reload_config)
