"""Services for ScreenLogic integration."""

import logging

from screenlogicpy import ScreenLogicError
from screenlogicpy.device_const.system import EQUIPMENT_FLAG
import voluptuous as vol

from homeassistant.core import HomeAssistant, ServiceCall, callback
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
from homeassistant.helpers import selector

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
def async_load_screenlogic_services(hass: HomeAssistant):
    """Set up services for the ScreenLogic integration."""

    def get_coordinator(
        service_call: ServiceCall,
    ) -> ScreenlogicDataUpdateCoordinator:
        if not (
            coordinator := hass.data[DOMAIN].get(service_call.data[ATTR_CONFIG_ENTRY])
        ):
            raise HomeAssistantError(
                f"Failed to call service '{service_call.service}'. Config entry for"
                " not found"
            )
        return coordinator

    async def async_set_color_mode(service_call: ServiceCall) -> None:
        coordinator: ScreenlogicDataUpdateCoordinator = get_coordinator(service_call)
        color_num = SUPPORTED_COLOR_MODES[service_call.data[ATTR_COLOR_MODE]]
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

    async def async_set_super_chlor(
        service_call: ServiceCall,
        is_on: bool,
        runtime: int | None = None,
    ) -> None:
        coordinator: ScreenlogicDataUpdateCoordinator = get_coordinator(service_call)
        if EQUIPMENT_FLAG.CHLORINATOR not in coordinator.gateway.equipment_flags:
            raise ServiceValidationError(
                f"Equipment configuration for {coordinator.gateway.name} does not support {service_call.service}"
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

    async def async_start_super_chlor(service_call: ServiceCall) -> None:
        runtime = service_call.data[ATTR_RUNTIME]
        await async_set_super_chlor(service_call, True, runtime)

    async def async_stop_super_chlor(service_call: ServiceCall) -> None:
        await async_set_super_chlor(service_call, False)

    hass.services.async_register(
        DOMAIN, SERVICE_SET_COLOR_MODE, async_set_color_mode, SET_COLOR_MODE_SCHEMA
    )

    hass.services.async_register(
        DOMAIN,
        SERVICE_START_SUPER_CHLORINATION,
        async_start_super_chlor,
        TURN_ON_SUPER_CHLOR_SCHEMA,
    )

    hass.services.async_register(
        DOMAIN,
        SERVICE_STOP_SUPER_CHLORINATION,
        async_stop_super_chlor,
        BASE_SERVICE_SCHEMA,
    )
