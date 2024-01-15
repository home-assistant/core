"""Services for ScreenLogic integration."""

import logging

from screenlogicpy import ScreenLogicError
import voluptuous as vol

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
def async_load_screenlogic_services(hass: HomeAssistant):
    """Set up services for the ScreenLogic integration."""
    if hass.services.has_service(DOMAIN, SERVICE_SET_COLOR_MODE):
        # Integration-level services have already been added. Return.
        return

    async def extract_screenlogic_config_entry_ids(service_call: ServiceCall):
        return [
            entry_id
            for entry_id in await async_extract_config_entry_ids(hass, service_call)
            if (entry := hass.config_entries.async_get_entry(entry_id))
            and entry.domain == DOMAIN
        ]

    async def async_set_color_mode(service_call: ServiceCall) -> None:
        if not (
            screenlogic_entry_ids := await extract_screenlogic_config_entry_ids(
                service_call
            )
        ):
            raise HomeAssistantError(
                f"Failed to call service '{SERVICE_SET_COLOR_MODE}'. Config entry for"
                " target not found"
            )
        color_num = SUPPORTED_COLOR_MODES[service_call.data[ATTR_COLOR_MODE]]
        for entry_id in screenlogic_entry_ids:
            coordinator: ScreenlogicDataUpdateCoordinator = hass.data[DOMAIN][entry_id]
            _LOGGER.debug(
                "Service %s called on %s with mode %s",
                SERVICE_SET_COLOR_MODE,
                coordinator.gateway.name,
                color_num,
            )
            try:
                await coordinator.gateway.async_set_color_lights(color_num)
                # Debounced refresh to catch any secondary
                # changes in the device
                await coordinator.async_request_refresh()
            except ScreenLogicError as error:
                raise HomeAssistantError(error) from error

    async def async_set_super_chlor(
        service_call: ServiceCall,
        is_on: bool,
        runtime: int | None = None,
    ) -> None:
        if not (
            screenlogic_entry_ids := await extract_screenlogic_config_entry_ids(
                service_call
            )
        ):
            raise HomeAssistantError(
                f"Failed to call service '{service_call.service}'. Config entry for"
                " target not found"
            )
        for entry_id in screenlogic_entry_ids:
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
                # Debounced refresh to catch any secondary
                # changes in the device
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
    )


@callback
def async_unload_screenlogic_services(hass: HomeAssistant):
    """Unload services for the ScreenLogic integration."""
    if hass.data[DOMAIN]:
        # There is still another config entry for this domain, don't remove services.
        return

    if not hass.services.async_services().get(DOMAIN):
        return

    _LOGGER.info("Unloading ScreenLogic Services")
    hass.services.async_remove(domain=DOMAIN, service=SERVICE_SET_COLOR_MODE)
    hass.services.async_remove(domain=DOMAIN, service=SERVICE_START_SUPER_CHLORINATION)
    hass.services.async_remove(domain=DOMAIN, service=SERVICE_STOP_SUPER_CHLORINATION)
