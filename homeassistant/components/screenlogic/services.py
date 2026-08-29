"""Services for ScreenLogic integration."""

import logging
from typing import cast

from screenlogicpy import ScreenLogicError
from screenlogicpy.device_const.system import EQUIPMENT_FLAG
import voluptuous as vol

from homeassistant.core import HomeAssistant, ServiceCall, callback
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
from homeassistant.helpers import selector, service

from .const import (
    ATTR_COLOR_MODE,
    ATTR_CONFIG_ENTRY,
    ATTR_RUNTIME,
    DOMAIN,
    MAX_RUNTIME,
    MIN_RUNTIME,
    SERVICE_SET_COLOR_MODE,
    SERVICE_START_SUPER_CHLORINATION,
    SERVICE_STOP_SUPER_CHLORINATION,
    SUPPORTED_COLOR_MODES,
)
from .coordinator import ScreenlogicDataUpdateCoordinator
from .types import ScreenLogicConfigEntry

_LOGGER = logging.getLogger(__name__)

BASE_SERVICE_SCHEMA = vol.Schema(
    {
        vol.Required(ATTR_CONFIG_ENTRY): selector.ConfigEntrySelector(
            {
                "integration": DOMAIN,
            }
        )
    }
)

SET_COLOR_MODE_SCHEMA = BASE_SERVICE_SCHEMA.extend(
    {
        vol.Required(ATTR_COLOR_MODE): vol.In(SUPPORTED_COLOR_MODES),
    }
)

TURN_ON_SUPER_CHLOR_SCHEMA = BASE_SERVICE_SCHEMA.extend(
    {
        vol.Optional(ATTR_RUNTIME, default=24): vol.All(
            vol.Coerce(int), vol.Clamp(min=MIN_RUNTIME, max=MAX_RUNTIME)
        ),
    }
)


@callback
def _get_coordinator(
    service_call: ServiceCall,
) -> ScreenlogicDataUpdateCoordinator:
    """Get the coordinator for the config entry targeted by a service call."""
    config_entry = cast(
        ScreenLogicConfigEntry,
        service.async_get_config_entry(
            service_call.hass, DOMAIN, service_call.data[ATTR_CONFIG_ENTRY]
        ),
    )
    return config_entry.runtime_data


async def _async_set_color_mode(service_call: ServiceCall) -> None:
    color_num = SUPPORTED_COLOR_MODES[service_call.data[ATTR_COLOR_MODE]]
    coordinator = _get_coordinator(service_call)
    _LOGGER.debug(
        "Service %s called on %s with mode %s",
        SERVICE_SET_COLOR_MODE,
        coordinator.gateway.name,
        color_num,
    )
    try:
        await coordinator.gateway.async_set_color_lights(color_num)
        # Debounced refresh to catch any secondary changes in the device
        await coordinator.async_request_refresh()
    except ScreenLogicError as error:
        raise HomeAssistantError(error) from error


async def _async_set_super_chlor(
    service_call: ServiceCall,
    is_on: bool,
    runtime: int | None = None,
) -> None:
    coordinator = _get_coordinator(service_call)
    if EQUIPMENT_FLAG.CHLORINATOR not in coordinator.gateway.equipment_flags:
        raise ServiceValidationError(
            f"Equipment configuration for {coordinator.gateway.name} does not"
            f" support {service_call.service}"
        )
    rt_log = f" with runtime {runtime}" if runtime else ""
    _LOGGER.debug(
        "Service %s called on %s%s",
        service_call.service,
        coordinator.gateway.name,
        rt_log,
    )
    try:
        await coordinator.gateway.async_set_scg_config(
            super_chlor_timer=runtime, super_chlorinate=is_on
        )
        # Debounced refresh to catch any secondary changes in the device
        await coordinator.async_request_refresh()
    except ScreenLogicError as error:
        raise HomeAssistantError(error) from error


async def _async_start_super_chlor(service_call: ServiceCall) -> None:
    runtime = service_call.data[ATTR_RUNTIME]
    await _async_set_super_chlor(service_call, True, runtime)


async def _async_stop_super_chlor(service_call: ServiceCall) -> None:
    await _async_set_super_chlor(service_call, False)


@callback
def async_setup_services(hass: HomeAssistant):
    """Set up services for the ScreenLogic integration."""

    hass.services.async_register(
        DOMAIN, SERVICE_SET_COLOR_MODE, _async_set_color_mode, SET_COLOR_MODE_SCHEMA
    )

    hass.services.async_register(
        DOMAIN,
        SERVICE_START_SUPER_CHLORINATION,
        _async_start_super_chlor,
        TURN_ON_SUPER_CHLOR_SCHEMA,
    )

    hass.services.async_register(
        DOMAIN,
        SERVICE_STOP_SUPER_CHLORINATION,
        _async_stop_super_chlor,
        BASE_SERVICE_SCHEMA,
    )
