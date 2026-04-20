"""Comet Blue Bluetooth integration."""

from __future__ import annotations

from bleak.exc import BleakError
from eurotronic_cometblue_ha import AsyncCometBlue

from homeassistant.components.bluetooth import async_ble_device_from_address
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_ADDRESS, CONF_PIN, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryError, ConfigEntryNotReady
from homeassistant.helpers import device_registry as dr

from .const import DOMAIN
from .coordinator import CometBlueConfigEntry, CometBlueDataUpdateCoordinator

PLATFORMS: list[Platform] = [
    Platform.BUTTON,
    Platform.CLIMATE,
    Platform.SENSOR,
]


async def async_setup_entry(hass: HomeAssistant, entry: CometBlueConfigEntry) -> bool:
    """Set up Eurotronic Comet Blue from a config entry."""

    address = entry.data[CONF_ADDRESS]

    ble_device = async_ble_device_from_address(hass, entry.data[CONF_ADDRESS])

    if not ble_device:
        raise ConfigEntryNotReady(
            f"Couldn't find a nearby device for address: {entry.data[CONF_ADDRESS]}"
        )

    cometblue_device = AsyncCometBlue(
        device=ble_device,
        pin=int(entry.data[CONF_PIN]),
    )
    try:
        async with cometblue_device:
            ble_device_info = await cometblue_device.get_device_info_async()
            try:
                # Device only returns battery level if PIN is correct
                await cometblue_device.get_battery_async()
            except TimeoutError as ex:
                # This likely means PIN was incorrect on Linux and ESPHome backends
                raise ConfigEntryError(
                    "Failed to read battery level, likely due to incorrect PIN"
                ) from ex
    except BleakError as ex:
        raise ConfigEntryNotReady(
            f"Failed to get device info from '{cometblue_device.device.address}'"
        ) from ex

    device_registry = dr.async_get(hass)
    device_registry.async_get_or_create(
        config_entry_id=entry.entry_id,
        identifiers={(DOMAIN, address)},
        name=f"{ble_device_info['model']} {cometblue_device.device.address}",
        manufacturer=ble_device_info["manufacturer"],
        model=ble_device_info["model"],
        sw_version=ble_device_info["version"],
    )

    coordinator = CometBlueDataUpdateCoordinator(
        hass,
        entry,
        cometblue_device,
    )
    await coordinator.async_config_entry_first_refresh()
    entry.runtime_data = coordinator

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
