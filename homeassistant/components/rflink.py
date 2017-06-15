"""
Support for Rflink components.

For more details about this component, please refer to the documentation at
https://home-assistant.io/components/rflink/
"""
import asyncio
from collections import defaultdict
import functools as ft
import logging

import async_timeout
import voluptuous as vol

from homeassistant.const import (
    ATTR_ENTITY_ID, CONF_HOST, CONF_PORT, EVENT_HOMEASSISTANT_STOP,
    STATE_UNKNOWN)
from homeassistant.core import CoreState, callback
from homeassistant.exceptions import HomeAssistantError
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.entity import Entity

REQUIREMENTS = ['rflink==0.0.34']

_LOGGER = logging.getLogger(__name__)

ATTR_EVENT = 'event'
ATTR_STATE = 'state'

CONF_ALIASSES = 'aliasses'
CONF_GROUP_ALIASSES = 'group_aliasses'
CONF_GROUP = 'group'
CONF_NOGROUP_ALIASSES = 'nogroup_aliasses'
CONF_DEVICE_DEFAULTS = 'device_defaults'
CONF_DEVICES = 'devices'
CONF_AUTOMATIC_ADD = 'automatic_add'
CONF_FIRE_EVENT = 'fire_event'
CONF_IGNORE_DEVICES = 'ignore_devices'
CONF_RECONNECT_INTERVAL = 'reconnect_interval'
CONF_SIGNAL_REPETITIONS = 'signal_repetitions'
CONF_WAIT_FOR_ACK = 'wait_for_ack'

DATA_DEVICE_REGISTER = 'rflink_device_register'
DATA_ENTITY_LOOKUP = 'rflink_entity_lookup'
DATA_ENTITY_GROUP_LOOKUP = 'rflink_entity_group_only_lookup'
DEFAULT_RECONNECT_INTERVAL = 10
DEFAULT_SIGNAL_REPETITIONS = 1
CONNECTION_TIMEOUT = 10

EVENT_BUTTON_PRESSED = 'button_pressed'
EVENT_KEY_COMMAND = 'command'
EVENT_KEY_ID = 'id'
EVENT_KEY_SENSOR = 'sensor'
EVENT_KEY_UNIT = 'unit'

RFLINK_GROUP_COMMANDS = ['allon', 'alloff']

DOMAIN = 'rflink'

DEVICE_DEFAULTS_SCHEMA = vol.Schema({
    vol.Optional(CONF_FIRE_EVENT, default=False): cv.boolean,
    vol.Optional(CONF_SIGNAL_REPETITIONS,
                 default=DEFAULT_SIGNAL_REPETITIONS): vol.Coerce(int),
})

CONFIG_SCHEMA = vol.Schema({
    DOMAIN: vol.Schema({
        vol.Required(CONF_PORT): vol.Any(cv.port, cv.string),
        vol.Optional(CONF_HOST, default=None): cv.string,
        vol.Optional(CONF_WAIT_FOR_ACK, default=True): cv.boolean,
        vol.Optional(CONF_RECONNECT_INTERVAL,
                     default=DEFAULT_RECONNECT_INTERVAL): int,
        vol.Optional(CONF_IGNORE_DEVICES, default=[]):
            vol.All(cv.ensure_list, [cv.string]),
    }),
}, extra=vol.ALLOW_EXTRA)


def identify_event_type(event):
    """Look at event to determine type of device.

    Async friendly.
    """
    if EVENT_KEY_COMMAND in event:
        return EVENT_KEY_COMMAND
    elif EVENT_KEY_SENSOR in event:
        return EVENT_KEY_SENSOR
    else:
        return 'unknown'


@asyncio.coroutine
def async_setup(hass, config):
    """Set up the Rflink component."""
    from rflink.protocol import create_rflink_connection
    import serial

    # Allow entities to register themselves by device_id to be looked up when
    # new rflink events arrive to be handled
    hass.data[DATA_ENTITY_LOOKUP] = {
        EVENT_KEY_COMMAND: defaultdict(list),
        EVENT_KEY_SENSOR: defaultdict(list),
    }
    hass.data[DATA_ENTITY_GROUP_LOOKUP] = {
        EVENT_KEY_COMMAND: defaultdict(list),
        EVENT_KEY_SENSOR: defaultdict(list),
    }

    # Allow platform to specify function to register new unknown devices
    hass.data[DATA_DEVICE_REGISTER] = {}

    @callback
    def event_callback(event):
        """Handle incoming Rflink events.

        Rflink events arrive as dictionaries of varying content
        depending on their type. Identify the events and distribute
        accordingly.
        """
        event_type = identify_event_type(event)
        _LOGGER.debug('event of type %s: %s', event_type, event)

        # Don't propagate non entity events (eg: version string, ack response)
        if event_type not in hass.data[DATA_ENTITY_LOOKUP]:
            _LOGGER.debug('unhandled event of type: %s', event_type)
            return

        # Lookup entities who registered this device id as device id or alias
        event_id = event.get('id', None)

        is_group_event = (event_type == EVENT_KEY_COMMAND and
                          event[EVENT_KEY_COMMAND] in RFLINK_GROUP_COMMANDS)
        if is_group_event:
            entities = hass.data[DATA_ENTITY_GROUP_LOOKUP][event_type].get(
                event_id, [])
        else:
            entities = hass.data[DATA_ENTITY_LOOKUP][event_type][event_id]

        if entities:
            # Propagate event to every entity matching the device id
            for entity in entities:
                _LOGGER.debug('passing event to %s', entities)
                entity.handle_event(event)
        else:
            _LOGGER.debug('device_id not known, adding new device')

            # If device is not yet known, register with platform (if loaded)
            if event_type in hass.data[DATA_DEVICE_REGISTER]:
                hass.async_run_job(
                    hass.data[DATA_DEVICE_REGISTER][event_type], event)

    # When connecting to tcp host instead of serial port (optional)
    host = config[DOMAIN][CONF_HOST]
    # TCP port when host configured, otherwise serial port
    port = config[DOMAIN][CONF_PORT]

    @callback
    def reconnect(exc=None):
        """Schedule reconnect after connection has been unexpectedly lost."""
        # Reset protocol binding before starting reconnect
        RflinkCommand.set_rflink_protocol(None)

        # If HA is not stopping, initiate new connection
        if hass.state != CoreState.stopping:
            _LOGGER.warning('disconnected from Rflink, reconnecting')
            hass.async_add_job(connect)

    @asyncio.coroutine
    def connect():
        """Set up connection and hook it into HA for reconnect/shutdown."""
        _LOGGER.info('Initiating Rflink connection')

        # Rflink create_rflink_connection decides based on the value of host
        # (string or None) if serial or tcp mode should be used

        # Initiate serial/tcp connection to Rflink gateway
        connection = create_rflink_connection(
            port=port,
            host=host,
            event_callback=event_callback,
            disconnect_callback=reconnect,
            loop=hass.loop,
            ignore=config[DOMAIN][CONF_IGNORE_DEVICES]
        )

        try:
            with async_timeout.timeout(CONNECTION_TIMEOUT,
                                       loop=hass.loop):
                transport, protocol = yield from connection

        except (serial.serialutil.SerialException, ConnectionRefusedError,
                TimeoutError, OSError, asyncio.TimeoutError) as exc:
            reconnect_interval = config[DOMAIN][CONF_RECONNECT_INTERVAL]
            _LOGGER.exception(
                "Error connecting to Rflink, reconnecting in %s",
                reconnect_interval)
            hass.loop.call_later(reconnect_interval, reconnect, exc)
            return

        # Bind protocol to command class to allow entities to send commands
        RflinkCommand.set_rflink_protocol(
            protocol, config[DOMAIN][CONF_WAIT_FOR_ACK])

        # handle shutdown of Rflink asyncio transport
        hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STOP,
                                   lambda x: transport.close())

        _LOGGER.info('Connected to Rflink')

    hass.async_add_job(connect)
    return True


class RflinkDevice(Entity):
    """Representation of a Rflink device.

    Contains the common logic for Rflink entities.
    """

    platform = None
    _state = STATE_UNKNOWN

    def __init__(self, device_id, hass, name=None, aliasses=None, group=True,
                 group_aliasses=None, nogroup_aliasses=None, fire_event=False,
                 signal_repetitions=DEFAULT_SIGNAL_REPETITIONS):
        """Initialize the device."""
        self.hass = hass

        # Rflink specific attributes for every component type
        self._device_id = device_id
        if name:
            self._name = name
        else:
            self._name = device_id

        self._should_fire_event = fire_event
        self._signal_repetitions = signal_repetitions

    def handle_event(self, event):
        """Handle incoming event for device type."""
        # Call platform specific event handler
        self._handle_event(event)

        # Propagate changes through ha
        self.hass.async_add_job(self.async_update_ha_state())

        # Put command onto bus for user to subscribe to
        if self._should_fire_event and identify_event_type(
                event) == EVENT_KEY_COMMAND:
            self.hass.bus.fire(EVENT_BUTTON_PRESSED, {
                ATTR_ENTITY_ID: self.entity_id,
                ATTR_STATE: event[EVENT_KEY_COMMAND],
            })
            _LOGGER.debug("Fired bus event for %s: %s",
                          self.entity_id, event[EVENT_KEY_COMMAND])

    def _handle_event(self, event):
        """Platform specific event handler."""
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


class RflinkCommand(RflinkDevice):
    """Singleton class to make Rflink command interface available to entities.

    This class is to be inherited by every Entity class that is actionable
    (switches/lights). It exposes the Rflink command interface for these
    entities.

    The Rflink interface is managed as a class level and set during setup (and
    reset on reconnect).
    """

    # Keep repetition tasks to cancel if state is changed before repetitions
    # are sent
    _repetition_task = None

    _protocol = None

    @classmethod
    def set_rflink_protocol(cls, protocol, wait_ack=None):
        """Set the Rflink asyncio protocol as a class variable."""
        cls._protocol = protocol
        if wait_ack is not None:
            cls._wait_ack = wait_ack

    @classmethod
    def is_connected(cls):
        """Return connection status."""
        return bool(cls._protocol)

    @asyncio.coroutine
    def _async_handle_command(self, command, *args):
        """Do bookkeeping for command, send it to rflink and update state."""
        self.cancel_queued_send_commands()

        if command == 'turn_on':
            cmd = 'on'
            self._state = True

        elif command == 'turn_off':
            cmd = 'off'
            self._state = False

        elif command == 'dim':
            # convert brightness to rflink dim level
            cmd = str(int(args[0] / 17))
            self._state = True

        elif command == 'toggle':
            cmd = 'on'
            # if the state is unknown or false, it gets set as true
            # if the state is true, it gets set as false
            self._state = self._state in [STATE_UNKNOWN, False]

        # Send initial command and queue repetitions.
        # This allows the entity state to be updated quickly and not having to
        # wait for all repetitions to be sent
        yield from self._async_send_command(cmd, self._signal_repetitions)

        # Update state of entity
        yield from self.async_update_ha_state()

    def cancel_queued_send_commands(self):
        """Cancel queued signal repetition commands.

        For example when user changed state while repetitions are still
        queued for broadcast. Or when a incoming Rflink command (remote
        switch) changes the state.
        """
        # cancel any outstanding tasks from the previous state change
        if self._repetition_task:
            self._repetition_task.cancel()

    @asyncio.coroutine
    def _async_send_command(self, cmd, repetitions):
        """Send a command for device to Rflink gateway."""
        _LOGGER.debug(
            "Sending command: %s to Rflink device: %s", cmd, self._device_id)

        if not self.is_connected():
            raise HomeAssistantError('Cannot send command, not connected!')

        if self._wait_ack:
            # Puts command on outgoing buffer then waits for Rflink to confirm
            # the command has been send out in the ether.
            yield from self._protocol.send_command_ack(self._device_id, cmd)
        else:
            # Puts command on outgoing buffer and returns straight away.
            # Rflink protocol/transport handles asynchronous writing of buffer
            # to serial/tcp device. Does not wait for command send
            # confirmation.
            self.hass.async_add_job(ft.partial(
                self._protocol.send_command, self._device_id, cmd))

        if repetitions > 1:
            self._repetition_task = self.hass.async_add_job(
                self._async_send_command(cmd, repetitions - 1))


class SwitchableRflinkDevice(RflinkCommand):
    """Rflink entity which can switch on/off (eg: light, switch)."""

    def _handle_event(self, event):
        """Adjust state if Rflink picks up a remote command for this device."""
        self.cancel_queued_send_commands()

        command = event['command']
        if command in ['on', 'allon']:
            self._state = True
        elif command in ['off', 'alloff']:
            self._state = False

    def async_turn_on(self, **kwargs):
        """Turn the device on."""
        return self._async_handle_command("turn_on")

    def async_turn_off(self, **kwargs):
        """Turn the device off."""
        return self._async_handle_command("turn_off")
