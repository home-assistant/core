"""The CCL Electronics integration."""

from __future__ import annotations

import logging

from aioccl import CCLServer

from homeassistant.components import webhook
from homeassistant.const import CONF_WEBHOOK_ID, Platform
from homeassistant.core import HomeAssistant, callback

from .coordinator import CCLConfigEntry, CCLCoordinator

_LOGGER = logging.getLogger(__name__)

PLATFORMS: list[Platform] = [Platform.SENSOR]


async def async_setup_entry(hass: HomeAssistant, entry: CCLConfigEntry) -> bool:
    """Set up a config entry for a single CCL device."""
    device = CCLServer.devices[entry.data[CONF_WEBHOOK_ID]]

    coordinator = entry.runtime_data = CCLCoordinator(hass, device, entry)

    @callback
    def push_update_callback(data) -> None:
        """Handle data pushed from the device."""
        coordinator.async_set_updated_data(data)

    device.set_update_callback(push_update_callback)

    await coordinator.async_config_entry_first_refresh()

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: CCLConfigEntry) -> bool:
    """Unload a config entry."""
    webhook.async_unregister(hass, entry.data[CONF_WEBHOOK_ID])

    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
