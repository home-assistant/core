"""The Switcher integration."""

from __future__ import annotations

import logging

from aioswitcher.bridge import SwitcherBridge
from aioswitcher.device import DeviceType, SwitcherBase

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    CONF_HOST,
    CONF_TOKEN,
    EVENT_HOMEASSISTANT_STOP,
    Platform,
)
from homeassistant.core import Event, HomeAssistant, callback
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers import device_registry as dr

from .const import CONF_DEVICE_ID, CONF_DEVICE_KEY, CONF_DEVICE_TYPE, DOMAIN
from .coordinator import (
    SwitcherDataUpdateCoordinator,
    SwitcherPollingDataUpdateCoordinator,
)
from .utils import async_test_device_connection

PLATFORMS = [
    Platform.BUTTON,
    Platform.CLIMATE,
    Platform.COVER,
    Platform.LIGHT,
    Platform.SENSOR,
    Platform.SWITCH,
]

_LOGGER = logging.getLogger(__name__)


type SwitcherConfigEntry = ConfigEntry[
    dict[str, SwitcherDataUpdateCoordinator | SwitcherPollingDataUpdateCoordinator]
]


async def async_setup_entry(hass: HomeAssistant, entry: SwitcherConfigEntry) -> bool:
    """Set up Switcher from a config entry."""

    token = entry.data.get(CONF_TOKEN)

    # Check if this is a manual configuration
    if CONF_HOST in entry.data:
        return await async_setup_manual_entry(hass, entry)

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


async def async_setup_manual_entry(
    hass: HomeAssistant, entry: SwitcherConfigEntry
) -> bool:
    """Set up Switcher from a manually configured entry."""

    ip_address = entry.data[CONF_HOST]
    device_id = entry.data[CONF_DEVICE_ID]
    device_key = entry.data[CONF_DEVICE_KEY]
    device_type_name = entry.data[CONF_DEVICE_TYPE]
    token = entry.data.get(CONF_TOKEN)

    # Convert device type name to DeviceType enum (e.g., "MINI" -> DeviceType.MINI)
    device_type = DeviceType[device_type_name]

    # Test connection to device using utility function
    try:
        await async_test_device_connection(
            ip_address,
            device_id,
            device_key,
            device_type,
        )
    except (TimeoutError, ValueError) as err:
        raise ConfigEntryNotReady(
            f"Unable to connect to Switcher device at {ip_address}"
        ) from err

    # Must be ready before dispatcher is called
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    # Create coordinator for manual device with polling
    coordinator = SwitcherPollingDataUpdateCoordinator(
        hass,
        entry,
        ip_address,
        device_id,
        device_key,
        device_type,
        token,
    )

    # Fetch initial data
    await coordinator.async_config_entry_first_refresh()

    coordinator.async_setup()
    entry.runtime_data = {device_id: coordinator}

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
