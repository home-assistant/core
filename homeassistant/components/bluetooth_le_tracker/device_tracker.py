"""Tracking for bluetooth low energy devices."""
from __future__ import annotations

import asyncio
from collections.abc import Callable
from datetime import datetime, timedelta
import logging
from uuid import UUID

import pygatt
import voluptuous as vol

from homeassistant.components.device_tracker import (
    PLATFORM_SCHEMA as PARENT_PLATFORM_SCHEMA,
)
from homeassistant.components.device_tracker.const import (
    CONF_SCAN_INTERVAL,
    CONF_TRACK_NEW,
    SCAN_INTERVAL,
    SOURCE_TYPE_BLUETOOTH_LE,
)
from homeassistant.components.device_tracker.legacy import (
    YAML_DEVICES,
    async_load_config,
)
from homeassistant.const import EVENT_HOMEASSISTANT_STOP
from homeassistant.core import HomeAssistant
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.event import track_point_in_utc_time
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


def setup_scanner(  # noqa: C901
    hass: HomeAssistant,
    config: ConfigType,
    see: Callable[..., None],
    discovery_info: DiscoveryInfoType | None = None,
) -> bool:
    """Set up the Bluetooth LE Scanner."""

    new_devices: dict[str, dict] = {}
    hass.data.setdefault(DATA_BLE, {DATA_BLE_ADAPTER: None})

    def handle_stop(event):
        """Try to shut down the bluetooth child process nicely."""
        # These should never be unset at the point this runs, but just for
        # safety's sake, use `get`.
        adapter = hass.data.get(DATA_BLE, {}).get(DATA_BLE_ADAPTER)
        if adapter is not None:
            adapter.kill()

    hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STOP, handle_stop)

    if config[CONF_TRACK_BATTERY]:
        battery_track_interval = config[CONF_TRACK_BATTERY_INTERVAL]
    else:
        battery_track_interval = timedelta(0)

    def see_device(address, name, new_device=False, battery=None):
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

        see(
            mac=BLE_PREFIX + address,
            host_name=name,
            source_type=SOURCE_TYPE_BLUETOOTH_LE,
            battery=battery,
        )

    def discover_ble_devices():
        """Discover Bluetooth LE devices."""
        _LOGGER.debug("Discovering Bluetooth LE devices")
        try:
            adapter = pygatt.GATTToolBackend()
            hass.data[DATA_BLE][DATA_BLE_ADAPTER] = adapter
            devs = adapter.scan()

            devices = {x["address"]: x["name"] for x in devs}
            _LOGGER.debug("Bluetooth LE devices discovered = %s", devices)
        except (RuntimeError, pygatt.exceptions.BLEError) as error:
            _LOGGER.error("Error during Bluetooth LE scan: %s", error)
            return {}
        return devices

    yaml_path = hass.config.path(YAML_DEVICES)
    devs_to_track = []
    devs_donot_track = []
    devs_track_battery = {}

    # Load all known devices.
    # We just need the devices so set consider_home and home range
    # to 0
    for device in asyncio.run_coroutine_threadsafe(
        async_load_config(yaml_path, hass, timedelta(0)), hass.loop
    ).result():
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

    interval = config.get(CONF_SCAN_INTERVAL, SCAN_INTERVAL)

    def update_ble(now):
        """Lookup Bluetooth LE devices and update status."""
        devs = discover_ble_devices()
        if devs_track_battery:
            adapter = hass.data[DATA_BLE][DATA_BLE_ADAPTER]
        for mac in devs_to_track:
            if mac not in devs:
                continue

            if devs[mac] is None:
                devs[mac] = mac

            battery = None
            if (
                mac in devs_track_battery
                and now > devs_track_battery[mac] + battery_track_interval
            ):
                handle = None
                try:
                    adapter.start(reset_on_start=False)
                    _LOGGER.debug("Reading battery for Bluetooth LE device %s", mac)
                    bt_device = adapter.connect(mac)
                    # Try to get the handle; it will raise a BLEError exception if not available
                    handle = bt_device.get_handle(BATTERY_CHARACTERISTIC_UUID)
                    battery = ord(bt_device.char_read(BATTERY_CHARACTERISTIC_UUID))
                    devs_track_battery[mac] = now
                except pygatt.exceptions.NotificationTimeout:
                    _LOGGER.warning("Timeout when trying to get battery status")
                except pygatt.exceptions.BLEError as err:
                    _LOGGER.warning("Could not read battery status: %s", err)
                    if handle is not None:
                        # If the device does not offer battery information, there is no point in asking again later on.
                        # Remove the device from the battery-tracked devices, so that their battery is not wasted
                        # trying to get an unavailable information.
                        del devs_track_battery[mac]
                finally:
                    adapter.stop()
            see_device(mac, devs[mac], battery=battery)

        if track_new:
            for address in devs:
                if address not in devs_to_track and address not in devs_donot_track:
                    _LOGGER.info("Discovered Bluetooth LE device %s", address)
                    see_device(address, devs[address], new_device=True)

        track_point_in_utc_time(hass, update_ble, dt_util.utcnow() + interval)

    update_ble(dt_util.utcnow())
    return True
