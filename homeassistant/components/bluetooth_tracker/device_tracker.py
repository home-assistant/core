"""Tracking for bluetooth devices."""
import logging
from typing import List, Set, Tuple

# pylint: disable=import-error
import bluetooth
from bt_proximity import BluetoothRSSI
import voluptuous as vol

from homeassistant.components.device_tracker import PLATFORM_SCHEMA
from homeassistant.components.device_tracker.const import (
    CONF_SCAN_INTERVAL,
    CONF_TRACK_NEW,
    DEFAULT_TRACK_NEW,
    DOMAIN,
    SCAN_INTERVAL,
    SOURCE_TYPE_BLUETOOTH,
)
from homeassistant.components.device_tracker.legacy import (
    YAML_DEVICES,
    async_load_config,
)
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.event import track_point_in_utc_time
from homeassistant.helpers.typing import HomeAssistantType
from homeassistant.util.async_ import run_coroutine_threadsafe
import homeassistant.util.dt as dt_util

_LOGGER = logging.getLogger(__name__)

BT_PREFIX = "BT_"

CONF_REQUEST_RSSI = "request_rssi"

CONF_DEVICE_ID = "device_id"

DEFAULT_DEVICE_ID = -1

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {
        vol.Optional(CONF_TRACK_NEW): cv.boolean,
        vol.Optional(CONF_REQUEST_RSSI): cv.boolean,
        vol.Optional(CONF_DEVICE_ID, default=DEFAULT_DEVICE_ID): vol.All(
            vol.Coerce(int), vol.Range(min=-1)
        ),
    }
)


def is_bluetooth_device(device) -> bool:
    """Check whether a device is a bluetooth device by its mac."""
    return device.mac and device.mac[:3].upper() == BT_PREFIX


def discover_devices(device_id: int) -> List[Tuple[str, str]]:
    """Discover Bluetooth devices."""
    result = bluetooth.discover_devices(
        duration=8,
        lookup_names=True,
        flush_cache=True,
        lookup_class=False,
        device_id=device_id,
    )
    _LOGGER.debug("Bluetooth devices discovered = %d", len(result))
    return result


def see_device(see, mac: str, device_name: str, rssi=None) -> None:
    """Mark a device as seen."""
    attributes = {}
    if rssi is not None:
        attributes["rssi"] = rssi
    see(
        mac=f"{BT_PREFIX}{mac}",
        host_name=device_name,
        attributes=attributes,
        source_type=SOURCE_TYPE_BLUETOOTH,
    )


def get_tracking_devices(hass: HomeAssistantType) -> Tuple[Set[str], Set[str]]:
    """
    Load all known devices.

    We just need the devices so set consider_home and home range to 0
    """
    yaml_path: str = hass.config.path(YAML_DEVICES)
    devices_to_track: Set[str] = set()
    devices_to_not_track: Set[str] = set()

    for device in run_coroutine_threadsafe(
        async_load_config(yaml_path, hass, 0), hass.loop
    ).result():
        # Check if device is a valid bluetooth device
        if not is_bluetooth_device(device):
            continue

        normalized_mac: str = device.mac[3:]
        if device.track:
            devices_to_track.add(normalized_mac)
        else:
            devices_to_not_track.add(normalized_mac)

    return devices_to_track, devices_to_not_track


def setup_scanner(hass: HomeAssistantType, config: dict, see, discovery_info=None):
    """Set up the Bluetooth Scanner."""
    device_id: int = config.get(CONF_DEVICE_ID)
    devices_to_track, devices_to_not_track = get_tracking_devices(hass)

    # If track new devices is true discover new devices on startup.
    track_new: bool = config.get(CONF_TRACK_NEW, DEFAULT_TRACK_NEW)
    _LOGGER.debug("Tracking new devices = %s", track_new)

    if not devices_to_track and not track_new:
        _LOGGER.debug("No Bluetooth devices to track and not tracking new devices")

    if track_new:
        for mac, device_name in discover_devices(device_id):
            if mac not in devices_to_track and mac not in devices_to_not_track:
                devices_to_track.add(mac)
                see_device(see, mac, device_name)

    interval = config.get(CONF_SCAN_INTERVAL, SCAN_INTERVAL)

    request_rssi = config.get(CONF_REQUEST_RSSI, False)
    if request_rssi:
        _LOGGER.debug("Detecting RSSI for devices")

    def update_bluetooth(_):
        """Update Bluetooth and set timer for the next update."""
        update_bluetooth_once()
        track_point_in_utc_time(hass, update_bluetooth, dt_util.utcnow() + interval)

    def update_bluetooth_once():
        """Lookup Bluetooth device and update status."""
        try:
            if track_new:
                for mac, device_name in discover_devices(device_id):
                    if mac not in devices_to_track and mac not in devices_to_not_track:
                        devices_to_track.add(mac)

            for mac in devices_to_track:
                _LOGGER.debug("Scanning %s", mac)
                device_name = bluetooth.lookup_name(mac, timeout=5)
                rssi = None
                if request_rssi:
                    client = BluetoothRSSI(mac)
                    rssi = client.request_rssi()
                    client.close()
                if device_name is None:
                    # Could not lookup device name
                    continue
                see_device(see, mac, device_name, rssi)
        except bluetooth.BluetoothError:
            _LOGGER.exception("Error looking up Bluetooth device")

    def handle_update_bluetooth(call):
        """Update bluetooth devices on demand."""
        update_bluetooth_once()

    update_bluetooth(dt_util.utcnow())

    hass.services.register(DOMAIN, "bluetooth_tracker_update", handle_update_bluetooth)

    return True
