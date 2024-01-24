"""Services for ScreenLogic integration."""

import logging

from screenlogicpy import ScreenLogicError
from screenlogicpy.device_const.system import EQUIPMENT_FLAG
import voluptuous as vol

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, ServiceCall, callback
from homeassistant.exceptions import HomeAssistantError
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.service import async_extract_config_entry_ids

from .const import (
    ATTR_COLOR_MODE,
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

SET_COLOR_MODE_SCHEMA = cv.make_entity_service_schema(
    {
        vol.Required(ATTR_COLOR_MODE): vol.In(SUPPORTED_COLOR_MODES),
    },
)

TURN_ON_SUPER_CHLOR_SCHEMA = cv.make_entity_service_schema(
    {
        vol.Optional(ATTR_RUNTIME, default=24): vol.Clamp(
            min=MIN_RUNTIME, max=MAX_RUNTIME
        ),
    }
)


@callback
def async_load_screenlogic_services(hass: HomeAssistant, entry: ConfigEntry):
    """Set up services for the ScreenLogic integration."""

    async def extract_screenlogic_config_entry_ids(service_call: ServiceCall):
        if not (
            screenlogic_entry_ids := [
                entry_id
                for entry_id in await async_extract_config_entry_ids(hass, service_call)
                if (entry := hass.config_entries.async_get_entry(entry_id))
                and entry.domain == DOMAIN
            ]
        ):
            raise HomeAssistantError(
                f"Failed to call service '{service_call.service}'. Config entry for"
                " target not found"
            )
        return screenlogic_entry_ids

    async def async_set_color_mode(service_call: ServiceCall) -> None:
        color_num = SUPPORTED_COLOR_MODES[service_call.data[ATTR_COLOR_MODE]]
        for entry_id in await extract_screenlogic_config_entry_ids(service_call):
            coordinator: ScreenlogicDataUpdateCoordinator = hass.data[DOMAIN][entry_id]
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
        for entry_id in await extract_screenlogic_config_entry_ids(service_call):
            coordinator: ScreenlogicDataUpdateCoordinator = hass.data[DOMAIN][entry_id]
            _LOGGER.debug(
                "Service %s called on %s with runtime %s",
                SERVICE_START_SUPER_CHLORINATION,
                coordinator.gateway.name,
                runtime,
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

    if not hass.services.has_service(DOMAIN, SERVICE_SET_COLOR_MODE):
        hass.services.async_register(
            DOMAIN, SERVICE_SET_COLOR_MODE, async_set_color_mode, SET_COLOR_MODE_SCHEMA
        )

    coordinator: ScreenlogicDataUpdateCoordinator = hass.data[DOMAIN][entry.entry_id]
    equipment_flags = coordinator.gateway.equipment_flags

    if EQUIPMENT_FLAG.CHLORINATOR in equipment_flags:
        if not hass.services.has_service(DOMAIN, SERVICE_START_SUPER_CHLORINATION):
            hass.services.async_register(
                DOMAIN,
                SERVICE_START_SUPER_CHLORINATION,
                async_start_super_chlor,
                TURN_ON_SUPER_CHLOR_SCHEMA,
            )

        if not hass.services.has_service(DOMAIN, SERVICE_STOP_SUPER_CHLORINATION):
            hass.services.async_register(
                DOMAIN,
                SERVICE_STOP_SUPER_CHLORINATION,
                async_stop_super_chlor,
            )


@callback
def async_unload_screenlogic_services(hass: HomeAssistant):
    """Unload services for the ScreenLogic integration."""

    if not hass.data[DOMAIN]:
        _LOGGER.debug("Unloading all ScreenLogic services")
        for service in hass.services.async_services_for_domain(DOMAIN):
            hass.services.async_remove(DOMAIN, service)
    elif not any(
        EQUIPMENT_FLAG.CHLORINATOR in coordinator.gateway.equipment_flags
        for coordinator in hass.data[DOMAIN].values()
    ):
        _LOGGER.debug("Unloading ScreenLogic chlorination services")
        hass.services.async_remove(DOMAIN, SERVICE_START_SUPER_CHLORINATION)
        hass.services.async_remove(DOMAIN, SERVICE_STOP_SUPER_CHLORINATION)
