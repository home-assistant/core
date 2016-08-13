"""Tracking for bluetooth devices."""
import logging
from datetime import timedelta

from homeassistant.helpers.event import track_point_in_utc_time
from homeassistant.components.device_tracker import (
    YAML_DEVICES,
    CONF_TRACK_NEW,
    CONF_SCAN_INTERVAL,
    DEFAULT_SCAN_INTERVAL,
    load_config,
)
import homeassistant.util as util
import homeassistant.util.dt as dt_util

_LOGGER = logging.getLogger(__name__)

REQUIREMENTS = ['gattlib']

BLE_PREFIX = 'BLE_'

def setup_scanner(hass, config, see):
    """Setup the BLE Scanner."""

    def see_device(address, name):
        """Mark a device as seen."""
        
        see(mac=BLE_PREFIX + address, host_name=name.strip("\x00"))

    def discover_ble_devices():
        """Discover Bluetooth LE devices."""
        from gattlib import DiscoveryService

        _LOGGER.debug("Discovering BLE devices")
        service = DiscoveryService()
        devices = service.discover(10)
        _LOGGER.debug("Bluetooth LE devices discovered = %s", devices)

        return devices

    yaml_path = hass.config.path(YAML_DEVICES)
    devs_to_track = []
    devs_donot_track = []

    # Load all known devices.
    # We just need the devices so set consider_home and home range
    # to 0
    for device in load_config(yaml_path, hass, 0, 0):
        # check if device is a valid bluetooth device
        if device.mac and device.mac[:3].upper() == BLE_PREFIX:
            if device.track:
                devs_to_track.append(device.mac[3:])
            else:
                devs_donot_track.append(device.mac[3:])

    # if track new devices is true discover new devices
    # on every scan.
    track_new = util.convert(config.get(CONF_TRACK_NEW), bool,
                             len(devs_to_track) == 0)
    if not devs_to_track and not track_new:
        _LOGGER.warning("No BLE devices to track!")
        return False

    interval = util.convert(config.get(CONF_SCAN_INTERVAL), int,
                            DEFAULT_SCAN_INTERVAL)

    def update_ble(now):
        """Lookup BLE bluetooth device and update status."""
        devs = discover_ble_devices()
        for mac in devs_to_track:
            _LOGGER.debug("Checking " + mac)
            result = mac in devs
            if not result:
                # Could not lookup device name
                continue
            see_device(mac, devs[mac])

        if track_new:
            for address in devs:
                if address not in devs_to_track and \
                  address not in devs_donot_track:
                    devs_to_track.append(address)
                    _LOGGER.info("Discovered BLE device %s", address)
                    see_device(address, devs[address])

        track_point_in_utc_time(hass, update_ble,
                                now + timedelta(seconds=interval))

    update_ble(dt_util.utcnow())

    return True
