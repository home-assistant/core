"""Support for Rflink components.

For more details about this component, please refer to the documentation at
https://home-assistant.io/components/rflink/

Technical overview:

The Rflink gateway is a USB serial device (Arduino with Rflink firwmare)
connected to a 433Mhz transceiver module.

The the `rflink` Python module a asyncio transport/protocol is setup that
fires an callback for every (valid/supported) packet received by the Rflink
gateway.

This component uses this callback to distribute 'rflink packet events' over
the HASS bus which can be subscribed to by entities/platform implementations.

The platform implementions take care of creating new devices (if enabled) for
unsees incoming packet id's.

Device Entities take care of matching to the packet id, interpreting and
performing actions based on the packet contents. Common entitiy logic is
maintained in this file.
"""
import asyncio
import logging

from homeassistant.const import EVENT_HOMEASSISTANT_STOP, STATE_UNKNOWN
from homeassistant.helpers.entity import Entity
from homeassistant.util import slugify

REQUIREMENTS = ['rflink==0.0.7']

DOMAIN = 'rflink'

RFLINK_EVENT = {
    'light': 'rflink_switch_packet_received',
    'sensor': 'rflink_sensor_packet_received',
    'switch': 'rflink_switch_packet_received',
    'send_command': 'rflink_send_command',
}

ATTR_PACKET = 'packet'
ATTR_COMMAND = 'command'

_LOGGER = logging.getLogger(__name__)


def serialize_id(packet):
    """Serialize packet identifiers into device id."""
    # invalid packet
    if not (packet.get('protocol') and packet.get('id')):
        return None

    return '_'.join(filter(None, [
        slugify(packet['protocol']),
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


def ignore_device(device_id, ignore_device_ids):
    """Validate device id with list of devices to ignore."""
    # don't fire if device is set to ignore
    for ignore in ignore_device_ids:
        if (ignore == device_id or
           (ignore.endswith('*') and device_id.startswith(ignore[:-1]))):
            return


@asyncio.coroutine
def async_setup(hass, config):
    """Setup the Rflink component."""
    from rflink.protocol import create_rflink_connection

    ignore_device_ids = config.get('ignore_devices', [])

    def packet_callback(packet):
        """Handle incoming rflink packets.

        Rflink packets arrive as dictionaries of varying content depending
        on their type. Identify the packets and distribute accordingly.
        """
        packet_type = identify_packet_type(packet)

        # fire bus event for packet type
        if not packet_type:
            _LOGGER.info(packet)
        elif packet_type in RFLINK_EVENT:
            device_id = serialize_id(packet)
            if not device_id:
                return

            if ignore_device(device_id, ignore_device_ids):
                return

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
    @asyncio.coroutine
    def send_command_ack(event):
        """Send command to rflink gateway via asyncio transport/protocol."""
        command = event.data[ATTR_COMMAND]
        yield from protocol.send_command_ack(*command)

    def send_command(event):
        """Send command to rflink gateway via asyncio transport/protocol."""
        command = event.data[ATTR_COMMAND]
        protocol.send_command(*command)

    if config.get('wait_for_ack', True):
        hass.bus.async_listen(RFLINK_EVENT['send_command'], send_command_ack)
    else:
        hass.bus.async_listen(RFLINK_EVENT['send_command'], send_command)

    # whoo
    return True


class RflinkDevice(Entity):
    """Represents a Rflink device.

    Contains the common logic for Rflink entities.
    """

    # should be set by component implementation
    domain = None
    # default state
    _state = STATE_UNKNOWN

    def __init__(self, device_id, hass, name=None, aliasses=[], icon=None):
        """Initialize the device."""
        self.hass = hass

        # rflink specific attributes for every component type
        self._device_id = device_id
        if name:
            self._name = name
        else:
            self._name = device_id
        # generate list of device_ids to match against
        self._aliasses = aliasses

        # optional attributes
        self._icon = icon

        # listen to component domain specific messages
        hass.bus.async_listen(RFLINK_EVENT[self.domain], lambda event:
                              self.match_packet(event.data[ATTR_PACKET]))

    def match_packet(self, packet):
        """Match and handle incoming packets.

        Match incoming packet to this device id
        or any of its aliasses (including wildcards).
        """
        device_id = serialize_id(packet)
        if device_id and (
            device_id == self._device_id or
                device_id in self._aliasses):
            self.handle_packet(packet)

    def handle_packet(self, packet):
        """Handle incoming packet for device type."""

        # call domain specific packet handler
        self._handle_packet(packet)

        # propagate changes through ha
        self.hass.async_add_job(self.async_update_ha_state())

    def _handle_packet(self, packet):
        """Domain specific packet handler."""
        raise NotImplementedError()

    @property
    def should_poll(self):
        """No polling needed."""
        return False

    @property
    def name(self):
        """Return a name for the device."""
        return self._name

    @property
    def is_on(self):
        """Return true if device is on."""
        return self._state

    @property
    def assumed_state(self):
        """Assume device state until first device packet sets state."""
        return self._state is STATE_UNKNOWN

    def _send_command(self, command, *args):
        """Send a command for this device to Rflink gateway."""
        if command == "turn_on":
            cmd = 'on'
            self._state = True

        elif command == 'turn_off':
            cmd = 'off'
            self._state = False

        elif command == 'dim':
            # convert brightness to rflink dim level
            cmd = str(int(args[0]/17))
            self._state = True

        # send protocol, device id, switch nr and command to rflink
        self.hass.bus.fire(
            RFLINK_EVENT['send_command'],
            {ATTR_COMMAND: self._device_id.split('_') + [cmd]}
        )
        # todo, wait for rflink ok response

        self.update_ha_state()


class SwitchableRflinkDevice(RflinkDevice):
    """Rflink entity which can switch on/off (eg: light, switch)."""

    def _handle_packet(self, packet):
        """Adjust state if Rflink picks up a remote command for this device."""
        command = packet['command']
        if command == 'on':
            self._state = True
        elif command == 'off':
            self._state = False

    def turn_on(self, **kwargs):
        """Turn the device on."""
        self._send_command("turn_on")

    def turn_off(self, **kwargs):
        """Turn the device off."""
        self._send_command("turn_off")
