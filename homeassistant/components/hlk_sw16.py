"""
Support for HLK-SW16 relay switch.

For more details about this component, please refer to the documentation at
https://home-assistant.io/components/hlk_sw16/
"""
import asyncio
import logging
import async_timeout

import voluptuous as vol

from homeassistant.const import (
    CONF_HOST, CONF_PORT,
    EVENT_HOMEASSISTANT_STOP, CONF_SWITCHES, CONF_NAME)
from homeassistant.core import CoreState, callback
from homeassistant.exceptions import HomeAssistantError
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.discovery import async_load_platform
from homeassistant.helpers.dispatcher import (
    async_dispatcher_send, async_dispatcher_connect)

REQUIREMENTS = ['hlk-sw16==0.0.2']

_LOGGER = logging.getLogger(__name__)

ATTR_EVENT = 'event'
ATTR_STATE = 'state'

CONF_RECONNECT_INTERVAL = 'reconnect_interval'

DATA_DEVICE_REGISTER = 'hlk_sw16_device_register'
DATA_ENTITY_LOOKUP = 'hlk_sw16_entity_lookup'
DEFAULT_RECONNECT_INTERVAL = 10
CONNECTION_TIMEOUT = 10

DOMAIN = 'hlk_sw16'

SIGNAL_AVAILABILITY = 'hlk_sw16_device_available'
SIGNAL_HANDLE_EVENT = 'hlk_sw16_handle_event_{}'

TMP_ENTITY = 'tmp.{}'

SWITCH_SCHEMA = vol.Schema({
    vol.Optional(CONF_NAME): cv.string,
})

RELAY_ID = vol.Any(0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 'a', 'b', 'c', 'd', 'e', 'f')

CONFIG_SCHEMA = vol.Schema({
    DOMAIN: vol.Schema({
        vol.Required(CONF_PORT): vol.Any(cv.port, cv.string),
        vol.Optional(CONF_HOST): cv.string,
        vol.Optional(CONF_RECONNECT_INTERVAL,
                     default=DEFAULT_RECONNECT_INTERVAL): int,
        vol.Required(CONF_SWITCHES): vol.Schema({RELAY_ID: SWITCH_SCHEMA}),
    }),
}, extra=vol.ALLOW_EXTRA)


async def async_setup(hass, config):
    """Set up the HLK-SW16 switch."""
    # Allow platform to specify function to register new unknown devices
    from hlk_sw16 import create_hlk_sw16_connection
    hass.data[DATA_DEVICE_REGISTER] = {}
    switches = config[DOMAIN][CONF_SWITCHES]

    host = config[DOMAIN][CONF_HOST]
    port = config[DOMAIN][CONF_PORT]

    @callback
    def reconnect():
        """Schedule reconnect after connection has been unexpectedly lost."""
        # Reset protocol binding before starting reconnect
        SW16Command.set_hlk_sw16_protocol(None)

        async_dispatcher_send(hass, SIGNAL_AVAILABILITY, False)

        # If HA is not stopping, initiate new connection
        if hass.state != CoreState.stopping:
            _LOGGER.warning('disconnected from HLK-SW16, reconnecting')
            hass.async_create_task(connect())

    async def connect():
        """Set up connection and hook it into HA for reconnect/shutdown."""
        _LOGGER.info('Initiating HLK-SW16 connection')

        try:
            with async_timeout.timeout(CONNECTION_TIMEOUT,
                                       loop=hass.loop):
                transport, protocol = await create_hlk_sw16_connection(
                    host=host,
                    port=port,
                    disconnect_callback=reconnect,
                    loop=hass.loop,
                    logger=_LOGGER)
                _LOGGER.info(transport)

        except (ConnectionRefusedError, TimeoutError, OSError,
                asyncio.TimeoutError) as exc:
            reconnect_interval = config[DOMAIN][CONF_RECONNECT_INTERVAL]
            _LOGGER.error(
                "Error connecting to HLK-SW16, reconnecting in %s",
                reconnect_interval)
            # Connection to HLK-SW16 device is lost, make entities unavailable
            async_dispatcher_send(hass, SIGNAL_AVAILABILITY, False)

            hass.loop.call_later(reconnect_interval, reconnect, exc)
            return

        # Load platforms
        for comp_name, comp_conf in switches.items():
            hass.async_create_task(
                async_load_platform(hass, 'switch', DOMAIN,
                                    (comp_name, comp_conf), config))

        # Bind protocol to command class to allow entities to send commands
        SW16Command.set_hlk_sw16_protocol(protocol)

        # handle shutdown of HLK-SW16 asyncio transport
        hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STOP,
                                   lambda x: transport.close())

        _LOGGER.info('Connected to HLK-SW16')

    hass.async_create_task(connect())
    return True


class SW16Device(Entity):
    """Representation of a HLK-SW16 device.

    Contains the common logic for HLK-SW16 entities.
    """

    platform = None
    _available = True

    def __init__(self, device_id, device_port, name=None):
        """Initialize the device."""
        # HLK-SW16 specific attributes for every component type
        self._device_id = device_id
        self._device_port = str(device_port)
        self._is_on = None
        if name:
            self._name = name
        else:
            self._name = device_id

    @callback
    def handle_event_callback(self, event):
        """Propagate changes through ha."""
        self.async_schedule_update_ha_state()

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
        return self._is_on

    @property
    def available(self):
        """Return True if entity is available."""
        return self._available

    @callback
    def _availability_callback(self, availability):
        """Update availability state."""
        self._available = availability
        self.async_schedule_update_ha_state()

    async def async_added_to_hass(self):
        """Register update callback."""
        async_dispatcher_connect(self.hass, SIGNAL_AVAILABILITY,
                                 self._availability_callback)


class SW16Command(SW16Device):
    """Singleton class to make HLK-SW16 command interface available to entities.

    This class is to be inherited by every Entity class that is actionable
    (switches/lights). It exposes the HLK-S16 command interface for these
    entities.

    The HLK-SW16 interface is managed as a class level and set during setup
    (and reset on reconnect).
    """

    _protocol = None

    @classmethod
    def set_hlk_sw16_protocol(cls, protocol):
        """Set the HLK-S16 asyncio protocol as a class variable."""
        cls._protocol = protocol

    @classmethod
    def is_connected(cls):
        """Return connection status."""
        return bool(cls._protocol)

    async def _async_handle_command(self, command, *args):
        """Do bookkeeping for command, send it to HLK-SW16 and update state."""
        if not self.is_connected():
            raise HomeAssistantError('Cannot send command, not connected!')

        if command == 'turn_on':
            state = await self._protocol.turn_on(self._device_port)
            _LOGGER.debug("Relay %s new state: %r", self._device_port, True)
            self._is_on = True
            # Update state of entity
            await self.async_update_ha_state()

        elif command == 'turn_off':
            state = await self._protocol.turn_off(self._device_port)
            _LOGGER.debug("Relay %s new state: %r", self._device_port, False)
            self._is_on = False
            # Update state of entity
            await self.async_update_ha_state()

        elif command == 'status':
            state = await self._protocol.status(self._device_port)
            _LOGGER.debug("Relay %s new state: %r", self._device_port, state)
            # Update state of entity
            self._is_on = state


class SwitchableSW16Device(SW16Command):
    """HLK-SW16 entity which can switch on/off (eg: light, switch)."""

    def _handle_event(self, event):
        """Adjust state if HLK-SW16 picks up a remote command."""
        command = event['command']
        if command in ['on', 'allon']:
            self._is_on = True
        elif command in ['off', 'alloff']:
            self._is_on = False

    async def async_update(self):
        """Get current switch status from the device."""
        return await self._async_handle_command("status")

    async def async_turn_on(self, **kwargs):
        """Turn the device on."""
        return await self._async_handle_command("turn_on")

    async def async_turn_off(self, **kwargs):
        """Turn the device off."""
        return await self._async_handle_command("turn_off")
