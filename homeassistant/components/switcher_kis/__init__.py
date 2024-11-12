"""The Switcher integration."""

from __future__ import annotations

import logging

from aioswitcher.bridge import SwitcherBridge
from aioswitcher.device import SwitcherBase

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_TOKEN, EVENT_HOMEASSISTANT_STOP, Platform
from homeassistant.core import Event, HomeAssistant, callback
from homeassistant.helpers import device_registry as dr

from .const import DOMAIN
from .coordinator import SwitcherDataUpdateCoordinator

PLATFORMS = [
    Platform.BUTTON,
    Platform.CLIMATE,
    Platform.COVER,
    Platform.LIGHT,
    Platform.SENSOR,
    Platform.SWITCH,
]

_LOGGER = logging.getLogger(__name__)


type SwitcherConfigEntry = ConfigEntry[dict[str, SwitcherDataUpdateCoordinator]]


async def async_setup_entry(hass: HomeAssistant, entry: SwitcherConfigEntry) -> bool:
    """Set up Switcher from a config entry."""

    token = entry.data.get(CONF_TOKEN)

    @callback
    def on_device_data_callback(device: SwitcherBase) -> None:
        """Use as a callback for device data."""

        coordinators = entry.runtime_data

        # Existing device update device data
        if coordinator := coordinators.get(device.device_id):
            coordinator.async_set_updated_data(device)
            return

        # New device - create device
        _LOGGER.info(
            "Discovered Switcher device - id: %s, key: %s, name: %s, type: %s (%s), is_token_needed: %s",
            device.device_id,
            device.device_key,
            device.name,
            device.device_type.value,
            device.device_type.hex_rep,
            device.token_needed,
        )

        if device.token_needed and not token:
            entry.async_start_reauth(hass)
            return

        coordinator = SwitcherDataUpdateCoordinator(hass, entry, device)
        coordinator.async_setup()
        coordinators[device.device_id] = coordinator

    # Must be ready before dispatcher is called
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    entry.runtime_data = {}
    bridge = SwitcherBridge(on_device_data_callback)
    await bridge.start()

    async def stop_bridge(event: Event | None = None) -> None:
        await bridge.stop()

    entry.async_on_unload(stop_bridge)

    entry.async_on_unload(
        hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STOP, stop_bridge)
    )

    return True


async def async_unload_entry(hass: HomeAssistant, entry: SwitcherConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)


async def async_remove_config_entry_device(
    hass: HomeAssistant, config_entry: SwitcherConfigEntry, device_entry: dr.DeviceEntry
) -> bool:
    """Remove a config entry from a device."""
    return not device_entry.identifiers.intersection(
        (DOMAIN, device_id) for device_id in config_entry.runtime_data
    )
