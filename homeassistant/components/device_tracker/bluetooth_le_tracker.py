"""Tracking for bluetooth low energy devices."""
import logging
from datetime import timedelta

import voluptuous as vol
from homeassistant.helpers.event import track_point_in_utc_time
from homeassistant.components.device_tracker import (
    YAML_DEVICES,
    CONF_TRACK_NEW,
    CONF_SCAN_INTERVAL,
    DEFAULT_SCAN_INTERVAL,
    PLATFORM_SCHEMA,
    load_config,
    DEFAULT_TRACK_NEW
)
import homeassistant.util as util
import homeassistant.util.dt as dt_util
import homeassistant.helpers.config_validation as cv

_LOGGER = logging.getLogger(__name__)

REQUIREMENTS = ['gattlib==0.20150805']

BLE_PREFIX = 'BLE_'
MIN_SEEN_NEW = 5
CONF_SCAN_DURATION = "scan_duration"

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Optional(CONF_SCAN_DURATION, default=10): cv.positive_int
})


def setup_scanner(hass, config, see):
    """Setup the Bluetooth LE Scanner."""
    # pylint: disable=import-error
    from gattlib import DiscoveryService

    new_devices = {}

    def see_device(address, name, new_device=False):
        """Mark a device as seen."""
        if new_device:
            if address in new_devices:
                _LOGGER.debug("Seen %s %s times", address,
                              new_devices[address])
                new_devices[address] += 1
                if new_devices[address] >= MIN_SEEN_NEW:
                    _LOGGER.debug("Adding %s to tracked devices", address)
                    devs_to_track.append(address)
                else:
                    return
            else:
                _LOGGER.debug("Seen %s for the first time", address)
                new_devices[address] = 1
                return

        see(mac=BLE_PREFIX + address, host_name=name.strip("\x00"))

    def discover_ble_devices():
        """Discover Bluetooth LE devices."""
        _LOGGER.debug("Discovering Bluetooth LE devices")
        try:
            service = DiscoveryService()
            devices = service.discover(duration)
            _LOGGER.debug("Bluetooth LE devices discovered = %s", devices)
        except RuntimeError as error:
            _LOGGER.error("Error during Bluetooth LE scan: %s", error)
            devices = []
        return devices

    yaml_path = hass.config.path(YAML_DEVICES)
    duration = config.get(CONF_SCAN_DURATION)
    devs_to_track = []
    devs_donot_track = []

    # Load all known devices.
    # We just need the devices so set consider_home and home range
    # to 0
    for device in load_config(yaml_path, hass, 0):
        # check if device is a valid bluetooth device
        if device.mac and device.mac[:4].upper() == BLE_PREFIX:
            if device.track:
                _LOGGER.debug("Adding %s to BLE tracker", device.mac)
                devs_to_track.append(device.mac[4:])
            else:
                _LOGGER.debug("Adding %s to BLE do not track", device.mac)
                devs_donot_track.append(device.mac[4:])

    # if track new devices is true discover new devices
    # on every scan.
    track_new = util.convert(config.get(CONF_TRACK_NEW), bool,
                             DEFAULT_TRACK_NEW)
    if not devs_to_track and not track_new:
        _LOGGER.warning("No Bluetooth LE devices to track!")
        return False

    interval = util.convert(config.get(CONF_SCAN_INTERVAL), int,
                            DEFAULT_SCAN_INTERVAL)

    def update_ble(now):
        """Lookup Bluetooth LE devices and update status."""
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
                    _LOGGER.info("Discovered Bluetooth LE device %s", address)
                    see_device(address, devs[address], new_device=True)

        track_point_in_utc_time(hass, update_ble,
                                now + timedelta(seconds=interval))

    update_ble(dt_util.utcnow())

    return True
