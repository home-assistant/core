"""Support for EQ3 devices."""

import logging
from typing import Any

from bleak.backends.device import BLEDevice
from bleak_esphome.backend.scanner import ESPHomeScanner
from eq3btsmart import Thermostat
from eq3btsmart.thermostat_config import ThermostatConfig

from homeassistant.components import bluetooth
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_MAC, CONF_NAME, CONF_SCAN_INTERVAL, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady

from .const import (
    CONF_ADAPTER,
    CONF_CURRENT_TEMP_SELECTOR,
    CONF_DEBUG_MODE,
    CONF_EXTERNAL_TEMP_SENSOR,
    CONF_TARGET_TEMP_SELECTOR,
    DEFAULT_ADAPTER,
    DEFAULT_CURRENT_TEMP_SELECTOR,
    DEFAULT_DEBUG_MODE,
    DEFAULT_SCAN_INTERVAL,
    DEFAULT_TARGET_TEMP_SELECTOR,
    DOMAIN,
    Adapter,
)
from .models import Eq3Config, Eq3ConfigEntry

PLATFORMS = [
    Platform.BINARY_SENSOR,
    Platform.BUTTON,
    Platform.CLIMATE,
    Platform.LOCK,
    Platform.NUMBER,
    Platform.SENSOR,
    Platform.SWITCH,
]

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Handle config entry setup."""

    mac_address: str = entry.data[CONF_MAC]
    name: str = entry.data[CONF_NAME]
    adapter: Adapter = entry.options.get(CONF_ADAPTER, DEFAULT_ADAPTER)
    current_temp_selector = entry.options.get(
        CONF_CURRENT_TEMP_SELECTOR, DEFAULT_CURRENT_TEMP_SELECTOR
    )
    target_temp_selector = entry.options.get(
        CONF_TARGET_TEMP_SELECTOR, DEFAULT_TARGET_TEMP_SELECTOR
    )
    external_temp_sensor = entry.options.get(CONF_EXTERNAL_TEMP_SENSOR)
    debug_mode = entry.options.get(CONF_DEBUG_MODE, DEFAULT_DEBUG_MODE)
    scan_interval = entry.options.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL)

    eq3_config = Eq3Config(
        mac_address=mac_address,
        name=name,
        adapter=adapter,
        current_temp_selector=current_temp_selector,
        target_temp_selector=target_temp_selector,
        external_temp_sensor=external_temp_sensor,
        debug_mode=debug_mode,
        scan_interval=scan_interval,
    )

    thermostat_config = ThermostatConfig(
        mac_address=mac_address,
        name=name,
        adapter=adapter,
        stay_connected=True,
    )

    device = await async_get_device(hass, eq3_config)

    thermostat = Thermostat(
        thermostat_config=thermostat_config,
        ble_device=device,
    )

    try:
        await thermostat.async_connect()
    except Exception as e:
        raise ConfigEntryNotReady(f"Could not connect to device: {e}") from e

    eq3_config_entry = Eq3ConfigEntry(eq3_config=eq3_config, thermostat=thermostat)

    domain_data: dict[str, Any] = hass.data.setdefault(DOMAIN, {})
    domain_data[entry.entry_id] = eq3_config_entry

    entry.async_on_unload(entry.add_update_listener(update_listener))
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Handle config entry unload."""

    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)

    if unload_ok:
        eq3_config_entry: Eq3ConfigEntry = hass.data[DOMAIN].pop(entry.entry_id)
        await eq3_config_entry.thermostat.async_disconnect()

    return unload_ok


async def update_listener(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Handle config entry update."""

    await hass.config_entries.async_reload(entry.entry_id)


async def async_get_device(hass: HomeAssistant, config: Eq3Config) -> BLEDevice:
    """Get the bluetooth device."""

    device: BLEDevice | None

    if config.adapter == Adapter.AUTO:
        device = bluetooth.async_ble_device_from_address(
            hass, config.mac_address, connectable=True
        )
        if device is None:
            raise ConfigEntryNotReady("Could not connect to device")
    else:
        scanner_devices = sorted(
            bluetooth.async_scanner_devices_by_address(
                hass=hass, address=config.mac_address, connectable=True
            ),
            key=lambda device_advertisement_data: device_advertisement_data.advertisement.rssi,
            reverse=True,
        )

        scanner_devices = [
            scanner_device
            for scanner_device in scanner_devices
            if not (isinstance(scanner_device.scanner, ESPHomeScanner))
        ]

        if config.adapter == Adapter.LOCAL:
            if len(scanner_devices) == 0:
                raise ConfigEntryNotReady("Could not connect to device")
            scanner_device = scanner_devices[0]
        else:  # adapter is e.g /org/bluez/hci0
            devices = [
                x
                for x in scanner_devices
                if (d := x.ble_device.details)
                and d.get("props", {}).get("Adapter") == config.adapter
            ]
            if len(devices) == 0:
                raise ConfigEntryNotReady("Could not connect to device")
            scanner_device = devices[0]
        device = scanner_device.ble_device

    return device
