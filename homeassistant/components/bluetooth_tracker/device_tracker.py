"""
Tracking for bluetooth devices.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/device_tracker.bluetooth_tracker/
"""
import logging

import voluptuous as vol

import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.event import track_point_in_utc_time
from homeassistant.components.device_tracker import (
    YAML_DEVICES, CONF_TRACK_NEW, CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL,
    load_config, PLATFORM_SCHEMA, DEFAULT_TRACK_NEW, SOURCE_TYPE_BLUETOOTH,
    DOMAIN)
import homeassistant.util.dt as dt_util

_LOGGER = logging.getLogger(__name__)

REQUIREMENTS = ['pybluez==0.22', 'bt_proximity==0.1.2']

BT_PREFIX = 'BT_'

CONF_REQUEST_RSSI = 'request_rssi'

CONF_DEVICE_ID = "device_id"

DEFAULT_DEVICE_ID = -1

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Optional(CONF_TRACK_NEW): cv.boolean,
    vol.Optional(CONF_REQUEST_RSSI): cv.boolean,
    vol.Optional(CONF_DEVICE_ID, default=DEFAULT_DEVICE_ID):
        vol.All(vol.Coerce(int), vol.Range(min=-1))
})


def setup_scanner(hass, config, see, discovery_info=None):
    """Set up the Bluetooth Scanner."""
    # pylint: disable=import-error
    import bluetooth
    from bt_proximity import BluetoothRSSI

    def see_device(mac, name, rssi=None):
        """Mark a device as seen."""
        attributes = {}
        if rssi is not None:
            attributes['rssi'] = rssi
        see(mac="{}{}".format(BT_PREFIX, mac), host_name=name,
            attributes=attributes, source_type=SOURCE_TYPE_BLUETOOTH)

    device_id = config.get(CONF_DEVICE_ID)

    def discover_devices():
        """Discover Bluetooth devices."""
        result = bluetooth.discover_devices(
            duration=8, lookup_names=True, flush_cache=True,
            lookup_class=False, device_id=device_id)
        _LOGGER.debug("Bluetooth devices discovered = %d", len(result))
        return result

    yaml_path = hass.config.path(YAML_DEVICES)
    devs_to_track = []
    devs_donot_track = []

    # Load all known devices.
    # We just need the devices so set consider_home and home range
    # to 0
    for device in load_config(yaml_path, hass, 0):
        # Check if device is a valid bluetooth device
        if device.mac and device.mac[:3].upper() == BT_PREFIX:
            if device.track:
                devs_to_track.append(device.mac[3:])
            else:
                devs_donot_track.append(device.mac[3:])

    # If track new devices is true discover new devices on startup.
    track_new = config.get(CONF_TRACK_NEW, DEFAULT_TRACK_NEW)
    if track_new:
        for dev in discover_devices():
            if dev[0] not in devs_to_track and \
                    dev[0] not in devs_donot_track:
                devs_to_track.append(dev[0])
                see_device(dev[0], dev[1])

    interval = config.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL)

    request_rssi = config.get(CONF_REQUEST_RSSI, False)

    def update_bluetooth(_):
        """Update Bluetooth and set timer for the next update."""
        update_bluetooth_once()
        track_point_in_utc_time(
            hass, update_bluetooth, dt_util.utcnow() + interval)

    def update_bluetooth_once():
        """Lookup Bluetooth device and update status."""
        try:
            if track_new:
                for dev in discover_devices():
                    if dev[0] not in devs_to_track and \
                            dev[0] not in devs_donot_track:
                        devs_to_track.append(dev[0])
            for mac in devs_to_track:
                _LOGGER.debug("Scanning %s", mac)
                result = bluetooth.lookup_name(mac, timeout=5)
                rssi = None
                if request_rssi:
                    rssi = BluetoothRSSI(mac).request_rssi()
                if result is None:
                    # Could not lookup device name
                    continue
                see_device(mac, result, rssi)
        except bluetooth.BluetoothError:
            _LOGGER.exception("Error looking up Bluetooth device")

    def handle_update_bluetooth(call):
        """Update bluetooth devices on demand."""
        update_bluetooth_once()

    update_bluetooth(dt_util.utcnow())

    hass.services.register(
        DOMAIN, "bluetooth_tracker_update", handle_update_bluetooth)

    return True
