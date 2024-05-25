"""The Switcher integration."""

from __future__ import annotations

import logging

from aioswitcher.device import SwitcherBase

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EVENT_HOMEASSISTANT_STOP, Platform
from homeassistant.core import Event, HomeAssistant, callback

from .const import DATA_DEVICE, DOMAIN
from .coordinator import SwitcherDataUpdateCoordinator
from .utils import async_start_bridge, async_stop_bridge

PLATFORMS = [
    Platform.BUTTON,
    Platform.CLIMATE,
    Platform.COVER,
    Platform.SENSOR,
    Platform.SWITCH,
]

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Switcher from a config entry."""
    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][DATA_DEVICE] = {}

    @callback
    def on_device_data_callback(device: SwitcherBase) -> None:
        """Use as a callback for device data."""

        # Existing device update device data
        if device.device_id in hass.data[DOMAIN][DATA_DEVICE]:
            coordinator: SwitcherDataUpdateCoordinator = hass.data[DOMAIN][DATA_DEVICE][
                device.device_id
            ]
            coordinator.async_set_updated_data(device)
            return

        # New device - create device
        _LOGGER.info(
            "Discovered Switcher device - id: %s, key: %s, name: %s, type: %s (%s)",
            device.device_id,
            device.device_key,
            device.name,
            device.device_type.value,
            device.device_type.hex_rep,
        )

        coordinator = hass.data[DOMAIN][DATA_DEVICE][device.device_id] = (
            SwitcherDataUpdateCoordinator(hass, entry, device)
        )
        coordinator.async_setup()

    # Must be ready before dispatcher is called
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    await async_start_bridge(hass, on_device_data_callback)

    async def stop_bridge(event: Event) -> None:
        await async_stop_bridge(hass)

    entry.async_on_unload(
        hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STOP, stop_bridge)
    )

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    await async_stop_bridge(hass)

    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        hass.data[DOMAIN].pop(DATA_DEVICE)

    return unload_ok
