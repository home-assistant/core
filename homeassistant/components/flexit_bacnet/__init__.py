"""The Flexit Nordic (BACnet) integration."""
from __future__ import annotations

import asyncio.exceptions

from flexit_bacnet import VENTILATION_MODE_STOP, DecodingError

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_DEVICE_ID, Platform
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.exceptions import HomeAssistantError

from .const import DOMAIN
from .coordinator import FlexitCoordinator

PLATFORMS: list[Platform] = [
    Platform.BINARY_SENSOR,
    Platform.CLIMATE,
    Platform.SENSOR,
    Platform.SWITCH,
]

SET_VENTILATION_MODE_OFF_SERVICE_NAME = "set_ventilation_mode_off"


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Flexit Nordic (BACnet) from a config entry."""

    device_id = entry.data[CONF_DEVICE_ID]

    coordinator = FlexitCoordinator(hass, device_id)
    await coordinator.async_config_entry_first_refresh()

    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = coordinator
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    # Register custom services
    async def handle_set_ventilation_mode_off(service: ServiceCall) -> None:
        """Handle the service call set_ventilation_mode_off."""
        try:
            await coordinator.device.set_ventilation_mode(VENTILATION_MODE_STOP)
        except (asyncio.exceptions.TimeoutError, ConnectionError, DecodingError) as exc:
            raise HomeAssistantError from exc
        finally:
            await coordinator.async_refresh()

    hass.services.async_register(
        DOMAIN,
        SET_VENTILATION_MODE_OFF_SERVICE_NAME,
        handle_set_ventilation_mode_off,
    )

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload the Flexit Nordic (BACnet) config entry."""
    if unload_ok := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        hass.data[DOMAIN].pop(entry.entry_id)

    return unload_ok
