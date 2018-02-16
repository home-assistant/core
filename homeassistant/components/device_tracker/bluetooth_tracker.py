"""
Tracking for bluetooth devices.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/device_tracker.bluetooth_tracker/
"""
import logging
import struct
import array
import fcntl

import voluptuous as vol

import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.event import track_point_in_utc_time
from homeassistant.components.device_tracker import (
    YAML_DEVICES, CONF_TRACK_NEW, CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL,
    load_config, PLATFORM_SCHEMA, DEFAULT_TRACK_NEW, SOURCE_TYPE_BLUETOOTH)
import homeassistant.util.dt as dt_util

_LOGGER = logging.getLogger(__name__)

REQUIREMENTS = ['pybluez==0.22']

BT_PREFIX = 'BT_'

CONF_REQUEST_RSSI = 'request_rssi'

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Optional(CONF_TRACK_NEW): cv.boolean,
    vol.Optional(CONF_REQUEST_RSSI): cv.boolean
})


def setup_scanner(hass, config, see, discovery_info=None):
    """Set up the Bluetooth Scanner."""
    # pylint: disable=import-error
    import bluetooth
    import bluetooth._bluetooth as bt

    class BluetoothRSSI(object):
        """Object class for getting the RSSI value of a Bluetooth address."""

        def __init__(self, addr):
            self.addr = addr
            self.hci_sock = bt.hci_open_dev()
            self.hci_fd = self.hci_sock.fileno()
            self.bt_sock = bluetooth.BluetoothSocket(bluetooth.L2CAP)
            self.bt_sock.settimeout(10)
            self.connected = False
            self.cmd_pkt = None

        def prep_cmd_pkt(self):
            """Prepare the command packet for requesting RSSI."""
            reqstr = struct.pack(
                b'6sB17s', bt.str2ba(self.addr), bt.ACL_LINK, b'\0' * 17)
            request = array.array('b', reqstr)
            handle = fcntl.ioctl(self.hci_fd, bt.HCIGETCONNINFO, request, 1)
            handle = struct.unpack(b'8xH14x', request.tostring())[0]
            self.cmd_pkt = struct.pack('H', handle)

        def connect(self):
            """Connect to the Bluetooth device."""
            # Connecting via PSM 1 - Service Discovery
            self.bt_sock.connect_ex((self.addr, 1))
            self.connected = True

        def request_rssi(self):
            """Request the current RSSI value.

            @return: The RSSI value or None if the device connection fails
                     (i.e. the device is not in range).
            """
            try:
                # Only do connection if not already connected
                if not self.connected:
                    self.connect()
                if self.cmd_pkt is None:
                    self.prep_cmd_pkt()
                # Send command to request RSSI
                rssi = bt.hci_send_req(
                    self.hci_sock, bt.OGF_STATUS_PARAM,
                    bt.OCF_READ_RSSI, bt.EVT_CMD_COMPLETE, 4, self.cmd_pkt)
                rssi = struct.unpack('b', rssi[3].to_bytes(1, 'big'))
                return rssi
            except IOError:
                # Happens if connection fails (e.g. device is not in range)
                self.connected = False
                return None

    def see_device(device):
        """Mark a device as seen."""
        attributes = {}
        if len(device) > 2:
            attributes['rssi'] = device[2]
        see(mac=BT_PREFIX + device[0], host_name=device[1],
            attributes=attributes, source_type=SOURCE_TYPE_BLUETOOTH)

    def discover_devices():
        """Discover Bluetooth devices."""
        result = bluetooth.discover_devices(
            duration=8, lookup_names=True, flush_cache=True,
            lookup_class=False)
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
                see_device(dev)

    interval = config.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL)

    request_rssi = config.get(CONF_REQUEST_RSSI, False)

    def update_bluetooth(now):
        """Lookup Bluetooth device and update status."""
        try:
            if track_new:
                for dev in discover_devices():
                    if dev[0] not in devs_to_track and \
                            dev[0] not in devs_donot_track:
                        devs_to_track.append(dev[0])
            for mac in devs_to_track:
                _LOGGER.debug("Scanning %s", mac)
                result = (bluetooth.lookup_name(mac, timeout=5),)
                if request_rssi:
                    rssi = BluetoothRSSI(mac).request_rssi()
                    if rssi is not None:
                        result = result + rssi
                if result[0] is None:
                    # Could not lookup device name
                    continue
                see_device((mac,) + result)
        except bluetooth.BluetoothError:
            _LOGGER.exception("Error looking up Bluetooth device")
        track_point_in_utc_time(
            hass, update_bluetooth, dt_util.utcnow() + interval)

    update_bluetooth(dt_util.utcnow())

    return True
