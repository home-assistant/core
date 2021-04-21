"""Services for ScreenLogic integration."""

import logging

from screenlogicpy import ScreenLogicError
import voluptuous as vol

from homeassistant.core import ServiceCall, callback
from homeassistant.exceptions import HomeAssistantError
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.service import async_extract_config_entry_ids
from homeassistant.helpers.typing import HomeAssistantType

from .const import (
    ATTR_COLOR_MODE,
    DOMAIN,
    SERVICE_SET_COLOR_MODE,
    SUPPORTED_COLOR_MODES,
)

_LOGGER = logging.getLogger(__name__)

SET_COLOR_MODE_SCHEMA = cv.make_entity_service_schema(
    {
        vol.Required(ATTR_COLOR_MODE): vol.In(SUPPORTED_COLOR_MODES),
    },
)


@callback
def async_load_screenlogic_services(hass: HomeAssistantType):
    """Set up services for the ScreenLogic integration."""
    if hass.services.has_service(DOMAIN, SERVICE_SET_COLOR_MODE):
        # Integration-level services have already been added. Return.
        return

    async def extract_screenlogic_config_entry_ids(service_call: ServiceCall):
        return [
            entry_id
            for entry_id in await async_extract_config_entry_ids(hass, service_call)
            if hass.config_entries.async_get_entry(entry_id).domain == DOMAIN
        ]

    async def async_set_color_mode(service_call: ServiceCall):
        if not (
            screenlogic_entry_ids := await extract_screenlogic_config_entry_ids(
                service_call
            )
        ):
            raise HomeAssistantError(
                f"Failed to call service '{SERVICE_SET_COLOR_MODE}'. Config entry for target not found"
            )
        color_num = SUPPORTED_COLOR_MODES[service_call.data[ATTR_COLOR_MODE]]
        for entry_id in screenlogic_entry_ids:
            coordinator = hass.data[DOMAIN][entry_id]["coordinator"]
            _LOGGER.debug(
                "Service %s called on %s with mode %s",
                SERVICE_SET_COLOR_MODE,
                coordinator.gateway.name,
                color_num,
            )
            try:
                async with coordinator.api_lock:
                    if not await hass.async_add_executor_job(
                        coordinator.gateway.set_color_lights, color_num
                    ):
                        raise HomeAssistantError(
                            f"Failed to call service '{SERVICE_SET_COLOR_MODE}'"
                        )
            except ScreenLogicError as error:
                raise HomeAssistantError(error) from error

    hass.services.async_register(
        DOMAIN, SERVICE_SET_COLOR_MODE, async_set_color_mode, SET_COLOR_MODE_SCHEMA
    )


@callback
def async_unload_screenlogic_services(hass: HomeAssistantType):
    """Unload services for the ScreenLogic integration."""
    if hass.data[DOMAIN]:
        # There is still another config entry for this domain, don't remove services.
        return

    if not hass.services.has_service(DOMAIN, SERVICE_SET_COLOR_MODE):
        return

    _LOGGER.info("Unloading ScreenLogic Services")
    hass.services.async_remove(domain=DOMAIN, service=SERVICE_SET_COLOR_MODE)
