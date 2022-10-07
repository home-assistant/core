"""Support for IntelliFire services."""
from __future__ import annotations

import voluptuous as vol

from homeassistant.core import HomeAssistant, ServiceCall

from .const import DOMAIN, LOGGER
from .coordinator import IntellifireDataUpdateCoordinator

ATTR_FLAME_HEIGHT = "height"

SERVICE_FLAME_HEIGHT = "flame_height"
SERVICE_FLAME_HEIGHT_SCHEMA = vol.Schema(
    {vol.Required(ATTR_FLAME_HEIGHT): vol.Any(0, 1, 2, 3, 4, 5)}
)


SERVICES = [SERVICE_FLAME_HEIGHT]


async def _setup_services(
    hass: HomeAssistant, coordinator: IntellifireDataUpdateCoordinator
) -> None:
    """Register IntelliFire Services."""

    async def flame_height(service_call: ServiceCall) -> None:
        """Set the flame height while converting to a zero based height for back end support."""
        height: int = service_call.data.get(ATTR_FLAME_HEIGHT, 0)
        if height == 0:
            LOGGER.debug("flame_height service will turn off fireplace")
            await coordinator.control_api.flame_off()
            await coordinator.control_api.set_flame_height(height=0)
        else:
            value_to_send = height - 1
            if not coordinator.read_api.data.is_on:
                LOGGER.debug("flame_height service will turn on fireplace")
                await coordinator.control_api.flame_on()

            LOGGER.debug(
                "flame_height service will set flame height to %d with raw value %s",
                height,
                value_to_send,
            )
            await coordinator.control_api.set_flame_height(height=value_to_send)

    hass.services.async_register(
        DOMAIN, SERVICE_FLAME_HEIGHT, flame_height, schema=SERVICE_FLAME_HEIGHT_SCHEMA
    )


def unload_services(hass: HomeAssistant) -> None:
    """Unload Renault services."""
    for service in SERVICES:
        hass.services.async_remove(DOMAIN, service)
