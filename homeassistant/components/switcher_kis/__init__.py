"""The Switcher integration."""

from __future__ import annotations

from dataclasses import dataclass
import logging

from aioswitcher.bridge import SwitcherBridge
from aioswitcher.device import SwitcherBase

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EVENT_HOMEASSISTANT_STOP, Platform
from homeassistant.core import Event, HomeAssistant, callback

from .coordinator import SwitcherDataUpdateCoordinator

PLATFORMS = [
    Platform.BUTTON,
    Platform.CLIMATE,
    Platform.COVER,
    Platform.SENSOR,
    Platform.SWITCH,
]

_LOGGER = logging.getLogger(__name__)


@dataclass
class SwitcherData:
    """Data for Switcher integration."""

    bridge: SwitcherBridge
    coordinators: dict[str, SwitcherDataUpdateCoordinator]


type SwitcherConfigEntry = ConfigEntry[SwitcherData]


async def async_setup_entry(hass: HomeAssistant, entry: SwitcherConfigEntry) -> bool:
    """Set up Switcher from a config entry."""

    @callback
    def on_device_data_callback(device: SwitcherBase) -> None:
        """Use as a callback for device data."""

        coordinators = entry.runtime_data.coordinators

        # Existing device update device data
        if coordinator := coordinators.get(device.device_id):
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

        coordinator = SwitcherDataUpdateCoordinator(hass, entry, device)
        coordinator.async_setup()
        coordinators[device.device_id] = coordinator

    # Must be ready before dispatcher is called
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    bridge = SwitcherBridge(on_device_data_callback)
    entry.runtime_data = SwitcherData(bridge=bridge, coordinators={})
    await bridge.start()

    async def stop_bridge(event: Event) -> None:
        await bridge.stop()

    entry.async_on_unload(
        hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STOP, stop_bridge)
    )

    return True


async def async_unload_entry(hass: HomeAssistant, entry: SwitcherConfigEntry) -> bool:
    """Unload a config entry."""
    await entry.runtime_data.bridge.stop()
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
