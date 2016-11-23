"""Support for Rflink components.

For more details about this component, please refer to the documentation at
https://home-assistant.io/components/rflink/
"""
import asyncio
import logging

from homeassistant.const import EVENT_HOMEASSISTANT_STOP
from homeassistant.helpers.entity import Entity

REQUIREMENTS = ['rflink==0.0.5']

DOMAIN = 'rflink'

RFLINK_EVENT = {
    'light': 'rflink_switch_packet_received',
    'sensor': 'rflink_sensor_packet_received',
    'send_command': 'rflink_send_command',
}

ATTR_PACKET = 'packet'
ATTR_COMMAND = 'command'

_LOGGER = logging.getLogger(__name__)


def serialize_id(packet):
    """Serialize packet identifiers into device id."""
    return '_'.join(filter(None, [
        packet['protocol'],
        packet['id'],
        packet.get('switch', None),
    ]))


def deserialize_id(device_id):
    """Split device id into dict of packet identifiers."""
    return device_id.split('_')


def identify_packet_type(packet):
    """Look at packet to determine type of device."""
    if 'switch' in packet:
        return 'light'
    elif 'temperature' in packet:
        return 'sensor'
    elif 'version' in packet:
        return 'informative'
    else:
        return 'unknown'


@asyncio.coroutine
def async_setup(hass, config):
    """Setup the Rflink component."""
    from rflink.protocol import create_rflink_connection

    def packet_callback(packet):
        """Handle incoming rflink packets.

        Rflink packets arrive as dictionaries of varying content depending
        on their type. Identify the packets and distribute accordingly.
        """
        packet_type = identify_packet_type(packet)
        if not packet_type:
            _LOGGER.info(packet)
        elif packet_type in RFLINK_EVENT:
            hass.bus.fire(RFLINK_EVENT[packet_type], {ATTR_PACKET: packet})
        else:
            _LOGGER.debug('unhandled packet of type: %s', packet_type)

    # when connecting to tcp host instead of serial port (optional)
    host = config[DOMAIN].get('host', None)
    # tcp port when host configured, otherwise serial port
    port = config[DOMAIN]['port']

    # initiate serial/tcp connection to Rflink gateway
    connection = create_rflink_connection(
        port=port,
        host=host,
        packet_callback=packet_callback,
        loop=hass.loop,
    )
    transport, protocol = yield from connection
    # handle shutdown of rflink asyncio transport
    hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STOP,
                               lambda x: transport.close())

    # provide channel for sending commands to rflink gateway
    def send_command(event):
        """Send command to rflink gateway via asyncio transport/protocol."""
        command = event.data[ATTR_COMMAND]
        protocol.send_command(*command)
    hass.bus.async_listen(RFLINK_EVENT['send_command'], send_command)

    # whoo
    return True


class RflinkDevice(Entity):
    """Represents a Rflink device.

    Contains the common logic for Rflink entities.
    """

    domain = None

    def __init__(self, name, device_id, hass):
        """Initialize the device."""
        self._name = name
        self._state = None
        self._device_id = device_id
        self.hass = hass

        if self.domain:
            hass.bus.async_listen(RFLINK_EVENT[self.domain], lambda event:
                                  self.match_packet(event.data[ATTR_PACKET]))

    def match_packet(self, packet):
        """Match and handle incoming packets.

        Match incoming packet to this device id
        and adjust state accordingly.
        """
        if serialize_id(packet) == self._device_id:
            self._handle_packet(packet)

    def _handle_packet(self, packet):
        """Handle incoming packet for device type."""
        command = packet['command']
        if command == 'on':
            self._state = True
        elif command == 'off':
            self._state = False

        self.hass.async_add_job(self.async_update_ha_state())

    @property
    def should_poll(self):
        """No polling needed."""
        return False

    @property
    def name(self):
        """Return a name for the device."""
        if self._name:
            return self._name
        else:
            return self._device_id

    @property
    def is_on(self):
        """Return true if device is on."""
        return self._state

    @property
    def assumed_state(self):
        """Assume device state until first device packet sets state."""
        return self._state is None

    def _send_command(self, command):
        """Send a command for this device."""
        if command == "turn_on":
            self._event(self._device_id.split('_') + ['on'])
            self._state = True

        elif command == 'turn_off':
            self._event(self._device_id.split('_') + ['off'])
            self._state = False

        self.update_ha_state()

    def _event(self, command):
        """Fire command event."""
        self.hass.bus.fire(
            RFLINK_EVENT['send_command'],
            {ATTR_COMMAND: command}
        )
