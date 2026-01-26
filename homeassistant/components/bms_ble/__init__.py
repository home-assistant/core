"""The BLE Battery Management System integration."""

from types import ModuleType
from typing import Final

from bleak.backends.device import BLEDevice

from homeassistant.components.bluetooth import async_ble_device_from_address
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryError, ConfigEntryNotReady
from homeassistant.helpers.importlib import async_import_module

from .const import DOMAIN, LOGGER
from .coordinator import BTBmsCoordinator

PLATFORMS: list[Platform] = [Platform.SENSOR]

type BTBmsConfigEntry = ConfigEntry[BTBmsCoordinator]


async def async_setup_entry(hass: HomeAssistant, entry: BTBmsConfigEntry) -> bool:
    """Set up BT Battery Management System from a config entry."""
    LOGGER.debug("Setup of %s", repr(entry))

    if entry.unique_id is None:
        raise ConfigEntryError(
            translation_domain=DOMAIN,
            translation_key="missing_unique_id",
        )

    ble_device: Final[BLEDevice | None] = async_ble_device_from_address(
        hass, entry.unique_id, True
    )

    if ble_device is None:
        LOGGER.debug("Failed to discover device %s via Bluetooth", entry.unique_id)
        raise ConfigEntryNotReady(
            translation_domain=DOMAIN,
            translation_key="device_not_found",
            translation_placeholders={
                "MAC": entry.unique_id,
            },
        )

    plugin: ModuleType = await async_import_module(hass, entry.data["type"])
    coordinator = BTBmsCoordinator(hass, ble_device, plugin.BMS(ble_device), entry)

    # Query the device the first time, initialise coordinator.data
    await coordinator.async_config_entry_first_refresh()
    entry.runtime_data = coordinator

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: BTBmsConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok: Final[bool] = await hass.config_entries.async_unload_platforms(
        entry, PLATFORMS
    )
    LOGGER.debug("Unloaded config entry: %s, ok? %s!", entry.unique_id, str(unload_ok))

    return unload_ok
