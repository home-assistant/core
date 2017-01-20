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

from homeassistant.const import (
    ATTR_ENTITY_ID, EVENT_HOMEASSISTANT_STOP, STATE_UNKNOWN)
from homeassistant.helpers.entity import Entity

REQUIREMENTS = ['rflink==0.0.18']

DOMAIN = 'rflink'

RFLINK_EVENT = {
    'light': 'rflink_switch_event_received',
    'sensor': 'rflink_sensor_event_received',
    'switch': 'rflink_switch_event_received',
    'send_command': 'rflink_send_command',
}

ATTR_EVENT = 'event'
ATTR_COMMAND = 'command'
DATA_KNOWN_DEVICES = 'rflink_known_device_ids'

_LOGGER = logging.getLogger(__name__)


def identify_event_type(event):
    """Look at event to determine type of device."""
    if 'command' in event:
        return 'light'
    elif 'sensor' in event:
        return 'sensor'
    else:
        return 'unknown'


@asyncio.coroutine
def async_setup(hass, config):
    """Setup the Rflink component."""
    from rflink.protocol import create_rflink_connection

    # initialize list of known devices
    hass.data[DATA_KNOWN_DEVICES] = []

    def event_callback(event):
        """Handle incoming rflink events.

        Rflink events arrive as dictionaries of varying content
        depending on their type. Identify the events and distribute
        accordingly.

        """
        event_type = identify_event_type(event)
        _LOGGER.info('event type %s', event_type)

        # fire bus event for event type
        if event_type in RFLINK_EVENT:
            hass.bus.fire(RFLINK_EVENT[event_type], {ATTR_EVENT: event})
        else:
            _LOGGER.debug('unhandled event of type: %s', event_type)

    # when connecting to tcp host instead of serial port (optional)
    host = config[DOMAIN].get('host', None)
    # tcp port when host configured, otherwise serial port
    port = config[DOMAIN]['port']

    # initiate serial/tcp connection to Rflink gateway
    connection = create_rflink_connection(
        port=port,
        host=host,
        event_callback=event_callback,
        loop=hass.loop,
        ignore=config[DOMAIN].get('ignore_devices', []),
    )
    transport, protocol = yield from connection
    # handle shutdown of rflink asyncio transport
    hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STOP,
                               lambda x: transport.close())

    # provide channel for sending commands to rflink gateway
    @asyncio.coroutine
    def send_command_ack(event):
        """Send command to rflink gateway via asyncio transport/protocol.

        Puts command on outgoing buffer then waits for Rflink to confirm
        the command has been send out in the ether.

        """
        yield from protocol.send_command_ack(
            event.data[ATTR_ENTITY_ID],
            event.data[ATTR_COMMAND],
        )

    def send_command(event):
        """Send command to rflink gateway via asyncio transport/protocol.

        Puts command on outgoing buffer and returns straight away.
        Rflink protocol/transport handles asynchronous writing of buffer
        to serial/tcp device. Does not wait for command send
        confirmation.

        """
        protocol.send_command(
            event.data[ATTR_ENTITY_ID],
            event.data[ATTR_COMMAND],
        )

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

    def __init__(self, device_id, hass, name=None, aliasses=None, icon=None):
        """Initialize the device."""
        self.hass = hass

        # rflink specific attributes for every component type
        self._device_id = device_id
        if name:
            self._name = name
        else:
            self._name = device_id

        # generate list of device_ids to match against
        if aliasses:
            self._aliasses = aliasses
        else:
            self._aliasses = []

        # optional attributes
        self._icon = icon

        # listen to component domain specific messages
        hass.bus.async_listen(RFLINK_EVENT[self.domain], lambda event:
                              self.match_event(event.data[ATTR_EVENT]))

    def match_event(self, event):
        """Match and handle incoming events.

        Match incoming event to this device id or any of its aliasses
        (including wildcards).

        """
        device_id = event.get('id', None)

        match = device_id == self._device_id
        match_alias = device_id in self._aliasses
        if match or match_alias:
            self.handle_event(event)

    def handle_event(self, event):
        """Handle incoming event for device type."""
        # call domain specific event handler
        self._handle_event(event)

        # propagate changes through ha
        self.hass.async_add_job(self.async_update_ha_state())

    def _handle_event(self, event):
        """Domain specific event handler."""
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
        if self.assumed_state:
            return False
        return self._state

    @property
    def assumed_state(self):
        """Assume device state until first device event sets state."""
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
            cmd = str(int(args[0] / 17))
            self._state = True

        # send protocol, device id, switch nr and command to rflink
        self.hass.bus.fire(
            RFLINK_EVENT['send_command'],
            {
                ATTR_ENTITY_ID: self._device_id,
                ATTR_COMMAND: cmd,
            }
        )

        # Update state of entity to represent the desired state even though we
        # do not have a confirmation yet the command has been successfully sent
        # by rflink.
        self.update_ha_state()


class SwitchableRflinkDevice(RflinkDevice):
    """Rflink entity which can switch on/off (eg: light, switch)."""

    def _handle_event(self, event):
        """Adjust state if Rflink picks up a remote command for this device."""
        command = event['command']
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
