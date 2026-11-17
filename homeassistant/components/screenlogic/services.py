"""Services for ScreenLogic integration."""

from enum import StrEnum
import logging
from typing import cast

import probatio
from screenlogicpy import ScreenLogicError
from screenlogicpy.device_const.system import EQUIPMENT_FLAG

from homeassistant.core import HomeAssistant, ServiceCall, callback
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
from homeassistant.helpers import selector, service

from .const import DOMAIN, MAX_RUNTIME, MIN_RUNTIME, SUPPORTED_COLOR_MODES
from .coordinator import ScreenLogicConfigEntry, ScreenlogicDataUpdateCoordinator


class ScreenLogicService(StrEnum):
    """Store keys for ScreenLogic services."""

    SET_COLOR_MODE = "set_color_mode"
    START_SUPER_CHLORINATION = "start_super_chlorination"
    STOP_SUPER_CHLORINATION = "stop_super_chlorination"


class ScreenLogicServiceArgument(StrEnum):
    """Store keys for ScreenLogic service arguments."""

    CONFIG_ENTRY = "config_entry"
    COLOR_MODE = "color_mode"
    RUNTIME = "runtime"


_LOGGER = logging.getLogger(__name__)

BASE_SERVICE_SCHEMA = probatio.Schema(
    {
        probatio.Required(
            ScreenLogicServiceArgument.CONFIG_ENTRY
        ): selector.ConfigEntrySelector(
            {
                "integration": DOMAIN,
            }
        )
    }
)

SET_COLOR_MODE_SCHEMA = BASE_SERVICE_SCHEMA.extend(
    {
        probatio.Required(ScreenLogicServiceArgument.COLOR_MODE): probatio.In(
            SUPPORTED_COLOR_MODES
        ),
    }
)

TURN_ON_SUPER_CHLOR_SCHEMA = BASE_SERVICE_SCHEMA.extend(
    {
        probatio.Optional(ScreenLogicServiceArgument.RUNTIME, default=24): probatio.All(
            probatio.Coerce(int), probatio.Clamp(min=MIN_RUNTIME, max=MAX_RUNTIME)
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
            service_call.hass,
            DOMAIN,
            service_call.data[ScreenLogicServiceArgument.CONFIG_ENTRY],
        ),
    )
    return config_entry.runtime_data


async def _async_set_color_mode(service_call: ServiceCall) -> None:
    color_num = SUPPORTED_COLOR_MODES[
        service_call.data[ScreenLogicServiceArgument.COLOR_MODE]
    ]
    coordinator = _get_coordinator(service_call)
    _LOGGER.debug(
        "Service %s called on %s with mode %s",
        ScreenLogicService.SET_COLOR_MODE,
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
    runtime = service_call.data[ScreenLogicServiceArgument.RUNTIME]
    await _async_set_super_chlor(service_call, True, runtime)


async def _async_stop_super_chlor(service_call: ServiceCall) -> None:
    await _async_set_super_chlor(service_call, False)


@callback
def async_setup_services(hass: HomeAssistant):
    """Set up services for the ScreenLogic integration."""

    hass.services.async_register(
        DOMAIN,
        ScreenLogicService.SET_COLOR_MODE,
        _async_set_color_mode,
        SET_COLOR_MODE_SCHEMA,
    )

    hass.services.async_register(
        DOMAIN,
        ScreenLogicService.START_SUPER_CHLORINATION,
        _async_start_super_chlor,
        TURN_ON_SUPER_CHLOR_SCHEMA,
    )

    hass.services.async_register(
        DOMAIN,
        ScreenLogicService.STOP_SUPER_CHLORINATION,
        _async_stop_super_chlor,
        BASE_SERVICE_SCHEMA,
    )
