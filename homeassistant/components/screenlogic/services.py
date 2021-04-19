"""Services for ScreenLogic integration."""

import logging

from screenlogicpy import ScreenLogicError
import voluptuous as vol

from homeassistant.const import ATTR_DEVICE_ID
from homeassistant.core import ServiceCall, callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import device_registry as dr
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.typing import HomeAssistantType

from .const import (
    ATTR_COLOR_MODE,
    DOMAIN,
    SERVICE_SET_COLOR_MODE,
    SUPPORTED_COLOR_MODES,
)

_LOGGER = logging.getLogger(__name__)

INTEGRATION_SERVICES = [SERVICE_SET_COLOR_MODE]

SET_COLOR_MODE_SCHEMA = vol.Schema(
    {
        vol.Required(ATTR_DEVICE_ID): cv.string,
        vol.Required(ATTR_COLOR_MODE): vol.In(SUPPORTED_COLOR_MODES),
    }
)


@callback
def async_load_screenlogic_services(hass: HomeAssistantType):
    """Set up services for the ScreenLogic integration."""
    existing_services = hass.services.async_services().get(DOMAIN)
    if existing_services and any(
        service in INTEGRATION_SERVICES for service in existing_services
    ):
        # Integration-level services have already been added. Return.
        return

    async def get_entry_id_for_device_id(device_id):
        device_registry = await dr.async_get_registry(hass)
        if (gateway_device_entry := device_registry.async_get(device_id)) is not None:
            for entry_id in gateway_device_entry.config_entries:
                config_entry = hass.config_entries.async_get_entry(entry_id)
                if config_entry.domain == DOMAIN:
                    return entry_id
        return None

    async def set_color_mode(service: ServiceCall):
        device_id = service.data.get(ATTR_DEVICE_ID)
        if (entry_id := await get_entry_id_for_device_id(device_id)) is None:
            raise HomeAssistantError(
                f"Failed to call service '{SERVICE_SET_COLOR_MODE}'. Config entry for Gateway device not found"
            )
        if (coordinator := hass.data[DOMAIN][entry_id]["coordinator"]) is None:
            raise HomeAssistantError(
                f"Failed to call service '{SERVICE_SET_COLOR_MODE}'. Gateway coordinator not found"
            )
        if (color_mode := service.data.get(ATTR_COLOR_MODE)) is None:
            raise ValueError(
                f"Failed to call service '{SERVICE_SET_COLOR_MODE}'. color_mode not found"
            )
        try:
            color_num = SUPPORTED_COLOR_MODES[color_mode]
            _LOGGER.debug(
                "Service %s called with mode %s", SERVICE_SET_COLOR_MODE, color_num
            )
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
        DOMAIN, SERVICE_SET_COLOR_MODE, set_color_mode, SET_COLOR_MODE_SCHEMA
    )


@callback
def async_unload_screenlogic_services(hass: HomeAssistantType):
    """Unload services for the ScreenLogic integration."""
    if hass.data[DOMAIN]:
        # There is still another config entry for this domain, don't remove services.
        return

    existing_services = hass.services.async_services().get(DOMAIN)
    if not existing_services or not any(
        service in INTEGRATION_SERVICES for service in existing_services
    ):
        return

    _LOGGER.info("Unloading ScreenLogic Services")
    hass.services.async_remove(domain=DOMAIN, service=SERVICE_SET_COLOR_MODE)
