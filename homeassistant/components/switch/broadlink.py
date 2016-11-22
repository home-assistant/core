"""
Support for Broadlink RM devices.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/switch.broadlink/
"""
import logging

import voluptuous as vol

from homeassistant.components.switch import (SwitchDevice, PLATFORM_SCHEMA)
from homeassistant.const import (
    CONF_FRIENDLY_NAME, CONF_SWITCHES, CONF_COMMAND_OFF,
    CONF_COMMAND_ON, CONF_OPTIMISTIC, CONF_HOST, CONF_MAC)
import homeassistant.helpers.config_validation as cv

_LOGGER = logging.getLogger(__name__)

SWITCH_SCHEMA = vol.Schema({
    vol.Optional(CONF_COMMAND_OFF, default='true'): cv.string,
    vol.Optional(CONF_COMMAND_ON, default='true'): cv.string,
    vol.Optional(CONF_FRIENDLY_NAME): cv.string,
    vol.Optional(CONF_OPTIMISTIC, default=True): cv.boolean,
})

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_SWITCHES): vol.Schema({cv.slug: SWITCH_SCHEMA}),
    vol.Required(CONF_HOST): cv.string,
    vol.Required(CONF_MAC): cv.string,
})


def setup_platform(hass, config, add_devices, discovery_info=None):
    """Setup Broadlink switches."""
    import binascii
    devices = config.get(CONF_SWITCHES, {})
    switches = []
    ip_addr = (config.get(CONF_HOST), 80)
    mac_addr = binascii.unhexlify(
        config.get(CONF_MAC).encode().replace(b':', b''))

    try:
        broadlink = Broadlink.Device(ip_addr, mac_addr)
        auth = broadlink.auth()
        if auth:
            _LOGGER.info('Broadlink connection successfully established.')

    except ValueError as error:
        _LOGGER.error(error)

    for object_id, device_config in devices.items():

        switches.append(
            BroadlinkSwitch(
                hass,
                object_id,
                device_config.get(CONF_FRIENDLY_NAME, object_id),
                device_config.get(CONF_COMMAND_ON),
                device_config.get(CONF_COMMAND_OFF),
                device_config.get(CONF_OPTIMISTIC),
                broadlink
            )
        )

    if not switches:
        _LOGGER.error("No switches added.")
        return False

    add_devices(switches)


class BroadlinkSwitch(SwitchDevice):
    """Representation of an Broadlink switch."""

    def __init__(self, hass, object_id, friendly_name, command_on,
                 command_off, optimistic, broadlink):
        """Initialize the switch."""
        self._hass = hass
        self._name = friendly_name
        self._state = False
        self._command_on = command_on
        self._command_off = command_off
        self._optimistic = optimistic
        self._broadlink = broadlink

    @staticmethod
    def _switch(command):
        """Execute the actual commands."""

    @property
    def name(self):
        """Return the name of the switch."""
        return self._name

    @property
    def is_on(self):
        """Return true if device is on."""
        return self._state

    @property
    def assumed_state(self):
        """Return if the state is based on assumptions."""
        return self._optimistic

    def update(self):
        """Update device state."""

    def turn_on(self, **kwargs):
        """Turn the device on."""
        import base64
        self._state = True
        _LOGGER.info("Running command: %s", self._command_on)
        auth = self._broadlink.auth()
        if auth:
            self._broadlink.send_data(base64.b64decode(self._command_on))

    def turn_off(self, **kwargs):
        """Turn the device off."""
        import base64
        self._state = False
        _LOGGER.info("Running command: %s", self._command_off)
        auth = self._broadlink.auth()
        if auth:
            self._broadlink.send_data(base64.b64decode(self._command_off))


class Broadlink():
    """Broadlink connector class."""

    class Device:
        """Broadlink Device."""

        def __init__(self, host, mac):
            """Initialize the object."""
            import socket
            import random
            import threading
            self.host = host
            self.mac = mac
            self.count = random.randrange(0xffff)

            self.key = b'\x09\x76\x28\x34\x3f\xe9\x9e'\
                       b'\x23\x76\x5c\x15\x13\xac\xcf\x8b\x02'
            self.ivr = b'\x56\x2e\x17\x99\x6d\x09\x3d\x28\xdd'\
                       b'\xb3\xba\x69\x5a\x2e\x6f\x58'

            self.ip_arr = bytearray([0, 0, 0, 0])
            self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
            self.sock.bind(('', 0))
            self.lock = threading.Lock()

        def auth(self):
            """Obtain the authentication key."""
            from Crypto.Cipher import AES
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

            aes = AES.new(bytes(self.key), AES.MODE_CBC, bytes(self.ivr))
            payload = aes.decrypt(bytes(enc_payload))

            if payload:
                self.ip_arr = payload[0x00:0x04]
                self.key = payload[0x04:0x14]
                return True
            else:
                _LOGGER.error('Connection to broadlink device has failed.')
                return False

        def send_packet(self, command, payload, timeout=5.0):
            """Send packet to Broadlink device."""
            import socket
            from Crypto.Cipher import AES
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
                packet[0x30] = self.ip_arr[0]
                packet[0x31] = self.ip_arr[1]
                packet[0x32] = self.ip_arr[2]
                packet[0x33] = self.ip_arr[3]
            except (IndexError, TypeError, NameError):
                _LOGGER.error('Invalid IP or MAC address.')
                return bytearray(0x30)

            checksum = 0xbeaf
            for i, _ in enumerate(payload):
                checksum += payload[i]
                checksum = checksum & 0xffff

            aes = AES.new(bytes(self.key), AES.MODE_CBC, bytes(self.ivr))
            payload = aes.encrypt(bytes(payload))

            packet[0x34] = checksum & 0xff
            packet[0x35] = checksum >> 8

            for i, _ in enumerate(payload):
                packet.append(payload[i])

            checksum = 0xbeaf
            for i, _ in enumerate(packet):
                checksum += packet[i]
                checksum = checksum & 0xffff
            packet[0x20] = checksum & 0xff
            packet[0x21] = checksum >> 8

            with self.lock:
                self.sock.sendto(packet, self.host)
                try:
                    self.sock.settimeout(timeout)
                    response = self.sock.recvfrom(1024)
                except socket.timeout:
                    _LOGGER.error("Socket timeout...")
                    return bytearray(0x30)

            return response[0]

        def send_data(self, data):
            """Send an IR or RF packet."""
            packet = bytearray([0x02, 0x00, 0x00, 0x00])
            packet += data
            self.send_packet(0x6a, packet)
