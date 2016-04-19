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

REQUIREMENTS = ['pybluez==0.22']

BT_PREFIX = 'BT_'


def setup_scanner(hass, config, see):
    """Setup the Bluetooth Scanner."""
    # pylint: disable=import-error
    import bluetooth

    def see_device(device):
        """Mark a device as seen."""
        see(mac=BT_PREFIX + device[0], host_name=device[1])

    def discover_devices():
        """Discover bluetooth devices."""
        result = bluetooth.discover_devices(duration=8,
                                            lookup_names=True,
                                            flush_cache=True,
                                            lookup_class=False)
        _LOGGER.debug("Bluetooth devices discovered = " + str(len(result)))
        return result

    yaml_path = hass.config.path(YAML_DEVICES)
    devs_to_track = []
    devs_donot_track = []

    # Load all known devices.
    # We just need the devices so set consider_home and home range
    # to 0
    for device in load_config(yaml_path, hass, 0, 0):
        # check if device is a valid bluetooth device
        if device.mac and device.mac[:3].upper() == BT_PREFIX:
            if device.track:
                devs_to_track.append(device.mac[3:])
            else:
                devs_donot_track.append(device.mac[3:])

    # if track new devices is true discover new devices
    # on startup.
    track_new = util.convert(config.get(CONF_TRACK_NEW), bool,
                             len(devs_to_track) == 0)
    if track_new:
        for dev in discover_devices():
            if dev[0] not in devs_to_track and \
               dev[0] not in devs_donot_track:
                devs_to_track.append(dev[0])
                see_device(dev)

    if not devs_to_track:
        _LOGGER.warning("No bluetooth devices to track!")
        return False

    interval = util.convert(config.get(CONF_SCAN_INTERVAL), int,
                            DEFAULT_SCAN_INTERVAL)

    def update_bluetooth(now):
        """Lookup bluetooth device and update status."""
        try:
            for mac in devs_to_track:
                _LOGGER.debug("Scanning " + mac)
                result = bluetooth.lookup_name(mac, timeout=5)
                if not result:
                    # Could not lookup device name
                    continue
                see_device((mac, result))
        except bluetooth.BluetoothError:
            _LOGGER.exception('Error looking up bluetooth device!')
        track_point_in_utc_time(hass, update_bluetooth,
                                now + timedelta(seconds=interval))

    update_bluetooth(dt_util.utcnow())

    return True
