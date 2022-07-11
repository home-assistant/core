"""Tracking for bluetooth low energy devices."""
from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from datetime import datetime, timedelta
import logging
from uuid import UUID

from bleak import BleakClient, BleakError
import voluptuous as vol

from homeassistant.components import bluetooth
from homeassistant.components.device_tracker import (
    PLATFORM_SCHEMA as PARENT_PLATFORM_SCHEMA,
)
from homeassistant.components.device_tracker.const import (
    CONF_TRACK_NEW,
    SOURCE_TYPE_BLUETOOTH_LE,
)
from homeassistant.components.device_tracker.legacy import (
    YAML_DEVICES,
    async_load_config,
)
from homeassistant.const import EVENT_HOMEASSISTANT_STOP
from homeassistant.core import Event, HomeAssistant, callback
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType
import homeassistant.util.dt as dt_util

_LOGGER = logging.getLogger(__name__)

# Base UUID: 00000000-0000-1000-8000-00805F9B34FB
# Battery characteristic: 0x2a19 (https://www.bluetooth.com/specifications/gatt/characteristics/)
BATTERY_CHARACTERISTIC_UUID = UUID("00002a19-0000-1000-8000-00805f9b34fb")
CONF_TRACK_BATTERY = "track_battery"
CONF_TRACK_BATTERY_INTERVAL = "track_battery_interval"
DEFAULT_TRACK_BATTERY_INTERVAL = timedelta(days=1)
DATA_BLE = "BLE"
DATA_BLE_ADAPTER = "ADAPTER"
BLE_PREFIX = "BLE_"
MIN_SEEN_NEW = 5

PLATFORM_SCHEMA = PARENT_PLATFORM_SCHEMA.extend(
    {
        vol.Optional(CONF_TRACK_BATTERY, default=False): cv.boolean,
        vol.Optional(
            CONF_TRACK_BATTERY_INTERVAL, default=DEFAULT_TRACK_BATTERY_INTERVAL
        ): cv.time_period,
    }
)


async def async_setup_scanner(
    hass: HomeAssistant,
    config: ConfigType,
    async_see: Callable[..., Awaitable[None]],
    discovery_info: DiscoveryInfoType | None = None,
) -> bool:
    """Set up the Bluetooth LE Scanner."""

    new_devices: dict[str, dict] = {}
    hass.data.setdefault(DATA_BLE, {DATA_BLE_ADAPTER: None})

    if config[CONF_TRACK_BATTERY]:
        battery_track_interval = config[CONF_TRACK_BATTERY_INTERVAL]
    else:
        battery_track_interval = timedelta(0)

    async def async_see_device(address, name, new_device=False, battery=None):
        """Mark a device as seen."""
        if name is not None:
            name = name.strip("\x00")

        if new_device:
            if address in new_devices:
                new_devices[address]["seen"] += 1
                if name:
                    new_devices[address]["name"] = name
                else:
                    name = new_devices[address]["name"]
                _LOGGER.debug("Seen %s %s times", address, new_devices[address]["seen"])
                if new_devices[address]["seen"] < MIN_SEEN_NEW:
                    return
                _LOGGER.debug("Adding %s to tracked devices", address)
                devs_to_track.append(address)
                if battery_track_interval > timedelta(0):
                    devs_track_battery[address] = dt_util.as_utc(
                        datetime.fromtimestamp(0)
                    )
            else:
                _LOGGER.debug("Seen %s for the first time", address)
                new_devices[address] = {"seen": 1, "name": name}
                return

        await async_see(
            mac=BLE_PREFIX + address,
            host_name=name,
            source_type=SOURCE_TYPE_BLUETOOTH_LE,
            battery=battery,
        )

    yaml_path = hass.config.path(YAML_DEVICES)
    devs_to_track = []
    devs_donot_track = []
    devs_track_battery = {}

    # Load all known devices.
    # We just need the devices so set consider_home and home range
    # to 0
    for device in await async_load_config(yaml_path, hass, timedelta(0)):
        # check if device is a valid bluetooth device
        if device.mac and device.mac[:4].upper() == BLE_PREFIX:
            address = device.mac[4:]
            if device.track:
                _LOGGER.debug("Adding %s to BLE tracker", device.mac)
                devs_to_track.append(address)
                if battery_track_interval > timedelta(0):
                    devs_track_battery[address] = dt_util.as_utc(
                        datetime.fromtimestamp(0)
                    )
            else:
                _LOGGER.debug("Adding %s to BLE do not track", device.mac)
                devs_donot_track.append(address)

    # if track new devices is true discover new devices
    # on every scan.
    track_new = config.get(CONF_TRACK_NEW)

    if not devs_to_track and not track_new:
        _LOGGER.warning("No Bluetooth LE devices to track!")
        return False

    async def _async_see_update_ble_battery(
        mac: str,
        now: datetime,
        service_info: bluetooth.BluetoothServiceInfo,
    ):
        """Lookup Bluetooth LE devices and update status."""
        battery = None
        try:
            async with BleakClient(mac) as client:
                bat_char = await client.read_gatt_char(BATTERY_CHARACTERISTIC_UUID)
                battery = ord(bat_char)
            # Try to get the handle; it will raise a BLEError exception if not available
        except asyncio.TimeoutError:
            _LOGGER.warning(
                "Timeout when trying to get battery status for %s", service_info.name
            )
        except BleakError as err:
            _LOGGER.debug("Could not read battery status: %s", err)
            # If the device does not offer battery information, there is no point in asking again later on.
            # Remove the device from the battery-tracked devices, so that their battery is not wasted
            # trying to get an unavailable information.
            del devs_track_battery[mac]
        if battery:
            await async_see_device(mac, service_info.name, battery=battery)

    @callback
    def _async_update_ble(
        service_info: bluetooth.BluetoothServiceInfo, change: bluetooth.BluetoothChange
    ):
        """Update from a ble callback."""
        mac = service_info.address
        if mac in devs_to_track:
            now = dt_util.utcnow()
            hass.async_create_task(async_see_device(mac, service_info.name))
            if (
                mac in devs_track_battery
                and now > devs_track_battery[mac] + battery_track_interval
            ):
                devs_track_battery[mac] = now
                asyncio.create_task(
                    _async_see_update_ble_battery(mac, now, service_info)
                )

        if track_new:
            if mac not in devs_to_track and mac not in devs_donot_track:
                _LOGGER.info("Discovered Bluetooth LE device %s", mac)
                hass.async_create_task(
                    async_see_device(mac, service_info.name, new_device=True)
                )

    cancel = bluetooth.async_register_callback(hass, _async_update_ble, None)

    def handle_stop(event: Event) -> None:
        """Cancel the callback."""
        cancel()

    hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STOP, handle_stop)

    return True
