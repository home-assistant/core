"""
Support for the Broadlink RM2 Pro (only temperature) and A1 devices.
For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/sensor.broadlink/
"""

from Crypto.Cipher import AES
from datetime import timedelta
from homeassistant.components.sensor import PLATFORM_SCHEMA
from homeassistant.const import (CONF_HOST, CONF_MAC,
    CONF_MONITORED_CONDITIONS, CONF_NAME, TEMP_CELSIUS)

import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.entity import Entity
from homeassistant.util import Throttle
import voluptuous as vol
import binascii
import logging
import random
import socket
import threading

REQUIREMENTS = []

_LOGGER = logging.getLogger(__name__)

CONF_UPDATE_INTERVAL = 'update_interval'
DEVICE_DEFAULT_NAME = 'BL'

SENSOR_TYPES = {
    'temperature': ['Temperature', TEMP_CELSIUS],
    'air_quality': ['Air Quality', None],
    'humidity': ['Humidity', '%'],
    'light': ['Light', None],
    'noise': ['Noise', None]
}

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Optional(CONF_NAME, default=DEVICE_DEFAULT_NAME): vol.Coerce(str),
    vol.Optional(CONF_MONITORED_CONDITIONS, default=[]):
        vol.All(cv.ensure_list, [vol.In(SENSOR_TYPES)]),
    vol.Optional(CONF_UPDATE_INTERVAL, default=timedelta(seconds=300)): (
        vol.All(cv.time_period, cv.positive_timedelta)),
    vol.Required(CONF_HOST): cv.string,
    vol.Required(CONF_MAC): cv.string,
})


# pylint: disable=unused-argument
def setup_platform(hass, config, add_devices, discovery_info=None):
    """Setup the Broadlink device sensors."""

    broadlink_data = BroadlinkData(
                    config.get(CONF_UPDATE_INTERVAL),
                    config.get(CONF_HOST),
                    config.get(CONF_MAC))
                                    
    broadlink_data.update()

    dev = []
    
    for variable in config[CONF_MONITORED_CONDITIONS]:
        dev.append(BroadlinkSensor(
                    config.get(CONF_NAME),
                    broadlink_data,
                    variable,
                    SENSOR_TYPES[variable][0],
                    SENSOR_TYPES[variable][1]))

    add_devices(dev, True)


class BroadlinkSensor(Entity):
    """Representation of a Broadlink device sensor."""

    def __init__(self, name, broadlink_data, sensor_type, sensor_name, unit):
        """Initialize the sensor."""
        self._name = "%s %s" % (name, sensor_name)
        self._state = None
        self.type = sensor_type
        self.broadlink_data = broadlink_data
        self._unit_of_measurement = unit
        self.update()

    @property
    def name(self):
        """Return the name of the sensor."""
        return self._name

    @property
    def state(self):
        """Return the state of the sensor."""
        return self._state

    @property
    def unit_of_measurement(self):
        """Return the unit this state is expressed in."""
        return self._unit_of_measurement

    def update(self):
        self.broadlink_data.update()
        if self.broadlink_data.data is not None:
            if self.type == 'temperature':
                self._state = self.broadlink_data.data['temperature']
            elif self.type == 'air_quality':
                self._state = self.broadlink_data.data['air_quality']
            elif self.type == 'humidity':
                self._state = self.broadlink_data.data['humidity']
            elif self.type == 'light':
                self._state = self.broadlink_data.data['light']
            elif self.type == 'noise':
                self._state = self.broadlink_data.data['noise']


class BroadlinkData(object):
    def __init__(self, interval, host, mac):
        self.data = None
        self._host = host
        self._mac = mac
        self.update = Throttle(interval)(self._update)

    def _update(self):
        try:
            ip_addr = (self._host, 80)
            mac_addr = binascii.unhexlify(self._mac.encode().replace(b':', b''))
            self.device = broadlink.device(ip_addr, mac_addr)
            self.auth = self.device.auth()
            if self.auth:
                self.data = self.device.check_sensors()
            else:
                self.data = None
        except ValueError as error:
            _LOGGER.error(error)


class broadlink():
    class device:
        def __init__(self, host, mac):
            self.host = host
            self.mac = mac
            self.count = random.randrange(0xffff)
            self.key = b'\x09\x76\x28\x34\x3f\xe9\x9e\x23\x76\x5c\x15\x13\xac\xcf\x8b\x02'
            self.iv = b'\x56\x2e\x17\x99\x6d\x09\x3d\x28\xdd\xb3\xba\x69\x5a\x2e\x6f\x58'
            self.id = bytearray([0, 0, 0, 0])
            self.cs = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            self.cs.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            self.cs.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
            self.cs.bind(('', 0))
            self.lock = threading.Lock()

        def auth(self):
            payload = bytearray(0x50)
            payload[0x04] = 0x31
            payload[0x05] = 0x31
            payload[0x06] = 0x31
            payload[0x07] = 0x31
            payload[0x08] = 0x31
            payload[0x09] = 0x31
            payload[0x0a] = 0x31
            payload[0x0b] = 0x31
            payload[0x0c] = 0x31
            payload[0x0d] = 0x31
            payload[0x0e] = 0x31
            payload[0x0f] = 0x31
            payload[0x10] = 0x31
            payload[0x11] = 0x31
            payload[0x12] = 0x31
            payload[0x1e] = 0x01
            payload[0x2d] = 0x01
            payload[0x30] = ord('T')
            payload[0x31] = ord('e')
            payload[0x32] = ord('s')
            payload[0x33] = ord('t')
            payload[0x34] = ord(' ')
            payload[0x35] = ord(' ')
            payload[0x36] = ord('1')

            response = self.send_packet(0x65, payload)

            enc_payload = response[0x38:]

            aes = AES.new(bytes(self.key), AES.MODE_CBC, bytes(self.iv))
            payload = aes.decrypt(bytes(enc_payload))

            if payload:
                self.id = payload[0x00:0x04]
                self.key = payload[0x04:0x14]
                return True
            else:
                _LOGGER.error('Connection to broadlink device has failed.')
                return False

        def send_packet(self, command, payload, timeout=5.0):
            try:
                packet = bytearray(0x38)
                packet[0x00] = 0x5a
                packet[0x01] = 0xa5
                packet[0x02] = 0xaa
                packet[0x03] = 0x55
                packet[0x04] = 0x5a
                packet[0x05] = 0xa5
                packet[0x06] = 0xaa
                packet[0x07] = 0x55
                packet[0x24] = 0x2a
                packet[0x25] = 0x27
                packet[0x26] = command
                packet[0x28] = self.count & 0xff
                packet[0x29] = self.count >> 8
                packet[0x2a] = self.mac[0]
                packet[0x2b] = self.mac[1]
                packet[0x2c] = self.mac[2]
                packet[0x2d] = self.mac[3]
                packet[0x2e] = self.mac[4]
                packet[0x2f] = self.mac[5]
                packet[0x30] = self.id[0]
                packet[0x31] = self.id[1]
                packet[0x32] = self.id[2]
                packet[0x33] = self.id[3]
            except (IndexError, TypeError, NameError):
                _LOGGER.error('Invalid IP or MAC address.')
                return bytearray(0x30)

            checksum = 0xbeaf
            for i in range(len(payload)):
                checksum += payload[i]
                checksum = checksum & 0xffff

            aes = AES.new(bytes(self.key), AES.MODE_CBC, bytes(self.iv))
            payload = aes.encrypt(bytes(payload))

            packet[0x34] = checksum & 0xff
            packet[0x35] = checksum >> 8

            for i in range(len(payload)):
                packet.append(payload[i])

            checksum = 0xbeaf
            for i in range(len(packet)):
                checksum += packet[i]
                checksum = checksum & 0xffff
            packet[0x20] = checksum & 0xff
            packet[0x21] = checksum >> 8

            with self.lock:
                self.cs.sendto(packet, self.host)
                try:
                    self.cs.settimeout(timeout)
                    response = self.cs.recvfrom(1024)
                except socket.timeout:
                    _LOGGER.error("Socket timeout...")
                    return bytearray(0x30)

            return response[0]

        def check_sensors(self):
            packet = bytearray(16)
            packet[0] = 1
            response = self.send_packet(0x6a, packet)
            err = response[0x22] | (response[0x23] << 8)
            if err == 0:
                data = {}
                aes = AES.new(bytes(self.key), AES.MODE_CBC, bytes(self.iv))
                payload = aes.decrypt(bytes(response[0x38:]))
                data['temperature'] = (payload[0x4] * 10 + payload[0x5]) / 10.0
                data['humidity'] = (payload[0x6] * 10 + payload[0x7]) / 10.0
                light = payload[0x8]
                if light == 0:
                    data['light'] = 'dark'
                elif light == 1:
                    data['light'] = 'dim'
                elif light == 2:
                    data['light'] = 'normal'
                elif light == 3:
                    data['light'] = 'bright'
                else:
                    data['light'] = 'unknown'
                air_quality = payload[0x0a]
                if air_quality == 0:
                    data['air_quality'] = 'excellent'
                elif air_quality == 1:
                    data['air_quality'] = 'good'
                elif air_quality == 2:
                    data['air_quality'] = 'normal'
                elif air_quality == 3:
                    data['air_quality'] = 'bad'
                else:
                    data['air_quality'] = 'unknown'
                noise = payload[0xc]
                if noise == 0:
                    data['noise'] = 'quiet'
                elif noise == 1:
                    data['noise'] = 'normal'
                elif noise == 2:
                    data['noise'] = 'noisy'
                else:
                    data['noise'] = 'unknown'
            return data

        def check_data(self):
            packet = bytearray(16)
            packet[0] = 4
            response = self.send_packet(0x6a, packet)
            err = response[0x22] | (response[0x23] << 8)
            if err == 0:
                aes = AES.new(bytes(self.key), AES.MODE_CBC, bytes(self.iv))
                payload = aes.decrypt(bytes(response[0x38:]))
                return payload[0x04:]
