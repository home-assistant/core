"""The Govee Bluetooth BLE integration."""
from __future__ import annotations

from datetime import timedelta
import logging

from airthings_ble import AirthingsBluetoothDeviceData

from homeassistant.components import bluetooth
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_SCAN_INTERVAL, Platform
from homeassistant.core import HomeAssistant

from ...exceptions import ConfigEntryNotReady
from ...helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from .const import DOMAIN

PLATFORMS: list[Platform] = [Platform.SENSOR]

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Airthings BLE device from a config entry."""
    _LOGGER.debug("async setup entry")
    hass.data.setdefault(DOMAIN, {})
    address = entry.unique_id

    elevation = hass.config.elevation
    is_metric = hass.config.units.is_metric
    scan_interval = entry.data[CONF_SCAN_INTERVAL]
    assert address is not None

    ble_device = bluetooth.async_ble_device_from_address(hass, address.upper())

    if not ble_device:
        raise ConfigEntryNotReady(
            f"Could not find Airthings device with address {address}"
        )

    airthings = AirthingsBluetoothDeviceData(_LOGGER, elevation, is_metric)

    # airthings_ble = AirthingsBluetoothDeviceData(_LOGGER)
    async def _update_method():
        """Get data from Airthings BLE."""
        if ble_device.name is not entry.title:
            hass.config_entries.async_update_entry(
                entry, title=ble_device.name
            )

        try:
            data = await airthings.update_device(ble_device)
        except Exception as err:
            raise UpdateFailed(f"Unable to fetch data: {err}") from err

        return data

    coordinator = DataUpdateCoordinator(
        hass,
        _LOGGER,
        name=DOMAIN,
        update_method=_update_method,
        update_interval=timedelta(seconds=scan_interval),
    )

    await coordinator.async_config_entry_first_refresh()

    hass.data[DOMAIN][entry.entry_id] = coordinator

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    if unload_ok := await hass.config_entries.async_unload_platforms(
        entry, PLATFORMS
    ):
        hass.data[DOMAIN].pop(entry.entry_id)

    return unload_ok
