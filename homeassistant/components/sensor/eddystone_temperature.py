"""
Read temperature information from the TLM frame broadcasted by Eddystone
beacons.
Your beacons must be configured to transmit UID (for identification) and TLM
(for temperature) frames.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/sensor.eddystone_temperature/

Original version of this code (for Skybeacons) by anpetrov.
https://github.com/anpetrov/skybeacon
"""
import logging
import threading
import struct
import binascii

import voluptuous as vol

import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.entity import Entity
from homeassistant.components.sensor import PLATFORM_SCHEMA
from homeassistant.const import (
    CONF_NAME, TEMP_CELSIUS, STATE_UNKNOWN, EVENT_HOMEASSISTANT_STOP,
    CONF_NAMESPACE, CONF_INSTANCE, CONF_BT_DEVICE_ID, CONF_BEACONS)

REQUIREMENTS = ['pybluez==0.22']

_LOGGER = logging.getLogger(__name__)

BEACON_SCHEMA = vol.Schema({
    vol.Required(CONF_NAMESPACE): cv.string,
    vol.Required(CONF_INSTANCE): cv.string,
    vol.Optional(CONF_NAME): cv.string
})

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Optional(CONF_BT_DEVICE_ID, default=0): cv.positive_int,
    vol.Required(CONF_BEACONS): vol.Schema({cv.string: BEACON_SCHEMA}),
})

LE_META_EVENT = 0x3e
OGF_LE_CTL = 0x08
OCF_LE_SET_SCAN_ENABLE = 0x000C
EVT_LE_ADVERTISING_REPORT = 0x02


# pylint: disable=unused-argument
def setup_platform(hass, config, add_devices, discovery_info=None):
    """Validate configuration, create devices and start monitoring thread"""

    _LOGGER.debug("Setting up...")

    bt_device_id = config.get("bt_device_id")

    beacons = config.get("beacons")
    devices = []

    mon = Monitor(hass, bt_device_id)

    for dev_name, properties in beacons.items():
        namespace = convert_hex_string(properties, "namespace", 20)
        instance = convert_hex_string(properties, "instance", 12)
        name = properties.get(CONF_NAME, dev_name)

        if instance is None or namespace is None:
            _LOGGER.error("Skipping %s", dev_name)
            continue
        else:
            devices.append(EddystoneTemp(name, namespace, instance, mon))

    def monitor_stop(_service_or_event):
        """Stop the monitor thread."""
        _LOGGER.info("Stopping scanner for eddystone beacons")
        mon.terminate()


    if len(devices) > 0:
        mon.devices = devices
        add_devices(devices)
        mon.start()
        hass.bus.listen_once(EVENT_HOMEASSISTANT_STOP, monitor_stop)
    else:
        _LOGGER.warning("No devices were added")


def convert_hex_string(config, config_key, length):
    """Retrieve value from config, validate its length and
    convert to binary string."""

    string = config.get(config_key)
    if len(string) != length:
        _LOGGER.error("Error in config parameter \"%s\": Must be exactly %d "
                      "bytes. Device will not be added.",
                      config_key, length/2)
        return None
    else:
        return binascii.unhexlify(string)


class EddystoneTemp(Entity):
    """Representation of a temperature sensor."""

    def __init__(self, name, namespace, instance, mon):
        """Initialize a sensor."""
        self.mon = mon
        self._name = name
        self.namespace = namespace
        self.instance = instance
        self.bt_addr = None
        self.temperature = STATE_UNKNOWN

    @property
    def name(self):
        """Return the name of the sensor."""
        return self._name

    @property
    def state(self):
        """Return the state of the device."""
        return self.temperature

    @property
    def unit_of_measurement(self):
        """Return the unit the value is expressed in."""
        return TEMP_CELSIUS


class Monitor(threading.Thread):
    """Continously scan for BLE advertisements."""

    def __init__(self, hass, bt_device_id):
        """Construct interface object."""
        threading.Thread.__init__(self)
        self.daemon = False
        self.hass = hass
        self.keep_going = True

        # list of beacons to monitor
        self.devices = []
        # number of the bt device (hciX)
        self.bt_device_id = bt_device_id
        # bt socket
        self.socket = None


    def run(self):
        """Continously scan for BLE advertisements."""

        # pylint: disable=import-error
        import bluetooth._bluetooth as bluez

        self.socket = bluez.hci_open_dev(self.bt_device_id)
        self.toggle_scan(True)

        try:
            filtr = bluez.hci_filter_new()
            bluez.hci_filter_all_events(filtr)
            bluez.hci_filter_set_ptype(filtr, bluez.HCI_EVENT_PKT)
            self.socket.setsockopt(bluez.SOL_HCI, bluez.HCI_FILTER, filtr)

            _LOGGER.debug("Scanner started")

            while self.keep_going:

                pkt = self.socket.recv(255)
                event = pkt[1]
                subevent = pkt[3]
                if event == LE_META_EVENT and subevent == EVT_LE_ADVERTISING_REPORT:
                    # we have an BLE advertisement
                    self.process_packet(pkt)
        except:
            _LOGGER.error("Exception while scanning for beacons", exc_info=True)
            raise
        finally:
            self.toggle_scan(False)

    def toggle_scan(self, enable):
        """ Enable and disable BLE scanning """
        # pylint: disable=import-error
        import bluetooth._bluetooth as bluez

        if enable:
            command = struct.pack("<BB", 0x01, 0x00)
        else:
            command = struct.pack("<BB", 0x00, 0x00)
        bluez.hci_send_cmd(self.socket, OGF_LE_CTL, OCF_LE_SET_SCAN_ENABLE, command)


    def process_packet(self, pkt):
        """ Processes an BLE advertisement packet.
        First, we look for the unique ID which identifies Eddystone beacons.
        All other packets will be ignored. We then filter for UID and TLM
        frames. See https://github.com/google/eddystone/ for reference.

        If we find an UID frame the namespace and instance identifier are
        extracted and compared againt the user-supplied values.
        If there is a match, the bluetooth address associated to the
        advertisement will be saved. This is necessary to identify the TLM
        frames sent by this beacon as they do not contain the namespace and
        instance identifier.

        If we encounter an TLM frame, we check if the bluetooth address
        belongs to the beacon monitored. If yes, we can finally extract the
        temperature.
        """

        bt_addr = pkt[7:13]

        # strip bluetooth address and start parsing "length-type-value"
        # structure
        pkt = pkt[14:]
        for type_, data in self.parse_structure(pkt):
            # type 0x16: service data, 0xaa 0xfe: eddystone UUID
            #_LOGGER.debug("_type: %s data: %s", binascii.hexlify(type_), binascii.hexlify(data))
            if type_ == 0x16 and data[:2] == b"\xaa\xfe":
                # found eddystone beacon
                if data[2] == 0x00:
                    # UID frame
                    # need to extract namespace and instance
                    # and compare them against target value
                    namespace = data[4:14]
                    instance = data[14:20]

                    device = self.match_device(namespace, instance, bt_addr)
                    if device is not None:
                        # found bt address of monitored beacon
                        _LOGGER.debug("Found beacon at new address: %s",
                                      binascii.hexlify(bt_addr))
                        device.bt_addr = bt_addr

                elif data[2] == 0x20:
                    device = self.match_device_by_addr(bt_addr)
                    if device is not None:
                        # TLM frame from target beacon
                        temp = struct.unpack("<H", data[6:8])[0]
                        _LOGGER.debug("Received temperature for device %s: %d"
                                      , device.name, temp)
                        device.temperature = temp

    def match_device(self, namespace, instance, bt_addr):
        """Searches device list for beacon with supplied namespace
        and instance id. Returns object only if bluetooth address is
        different.
        """
        for dev in self.devices:
            if dev.namespace == namespace and dev.instance == instance \
            and (dev.bt_addr is None or dev.bt_addr != bt_addr):
                return dev
        return None

    def match_device_by_addr(self, bt_addr):
        """Searches device list for beacon with the supplied bluetooth
        address.
        """
        for dev in self.devices:
            if dev.bt_addr == bt_addr:
                return dev
        return None

    @staticmethod
    def parse_structure(data):
        """ Generator to parse the eddystone packet structure.
        | length | type |     data       |
        | 1 byte |1 byte| length-1 bytes |
        """
        while data:
            try:
                length, type_ = struct.unpack("BB", data[:2])
                value = data[2:1+length]
            except struct.error:
                break

            yield type_, value
            data = data[1+length:]

    def terminate(self):
        """Signal runner to stop and join thread."""
        self.keep_going = False
        self.join()
