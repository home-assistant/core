"""Comet Blue Bluetooth integration."""

from __future__ import annotations

import logging

from bleak.exc import BleakError
from eurotronic_cometblue_ha import AsyncCometBlue

from homeassistant.components.bluetooth import async_ble_device_from_address
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_ADDRESS, CONF_PIN, Platform
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.device_registry import DeviceInfo

from .const import DOMAIN
from .coordinator import CometBlueDataUpdateCoordinator

CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)
PLATFORMS: list[Platform] = [
    Platform.CLIMATE,
    Platform.NUMBER,
    Platform.SENSOR,
]
LOGGER = logging.getLogger(__name__)

type CometBlueConfigEntry = ConfigEntry[CometBlueDataUpdateCoordinator]


@callback
def _async_migrate_options_if_missing(hass: HomeAssistant, entry: ConfigEntry) -> None:
    data = dict(entry.data)

    changed = False

    for k in entry.data:
        if k not in {CONF_ADDRESS, CONF_PIN}:
            _ = data.pop(k, None)
            changed = True
    if CONF_PIN in entry.data and isinstance(entry.data[CONF_PIN], int):
        data[CONF_PIN] = f"{entry.data[CONF_PIN]:06d}"
        changed = True

    if changed:
        hass.config_entries.async_update_entry(entry, data=data)


async def async_setup_entry(hass: HomeAssistant, entry: CometBlueConfigEntry) -> bool:
    """Set up Eurotronic Comet Blue from a config entry."""

    _async_migrate_options_if_missing(hass, entry)

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
            device_info = DeviceInfo(
                identifiers={(DOMAIN, address)},
                name=f"{ble_device_info['model']} {cometblue_device.device.address}",
                sw_version=ble_device_info["version"],
                manufacturer=ble_device_info["manufacturer"],
                model=ble_device_info["model"],
            )
            try:
                # Device only returns battery level if PIN is correct
                await cometblue_device.get_battery_async()
            except Exception:
                # need to use broad exception as different exceptions are raised
                # based on the underlying OS and backend
                LOGGER.exception(
                    "Failed to read battery level, likely due to incorrect PIN"
                )
    except BleakError as ex:
        raise ConfigEntryNotReady(
            f"Failed to get device info from '{cometblue_device.device.address}'"
        ) from ex

    coordinator = CometBlueDataUpdateCoordinator(
        hass,
        entry,
        cometblue_device,
        device_info,
    )
    await coordinator.async_config_entry_first_refresh()
    entry.runtime_data = coordinator

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    if unload_ok := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        coordinator: CometBlueDataUpdateCoordinator = entry.runtime_data
        await coordinator.async_shutdown()

    return unload_ok
