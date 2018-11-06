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
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.discovery import async_load_platform
from homeassistant.helpers.dispatcher import (
    async_dispatcher_send, async_dispatcher_connect)

REQUIREMENTS = ['hlk-sw16==0.0.3']

_LOGGER = logging.getLogger(__name__)

ATTR_EVENT = 'event'
ATTR_STATE = 'state'

CONF_RECONNECT_INTERVAL = 'reconnect_interval'

DATA_DEVICE_REGISTER = 'hlk_sw16_device_register'
DEFAULT_RECONNECT_INTERVAL = 10
CONNECTION_TIMEOUT = 10
DEFAULT_PORT = 8080

DOMAIN = 'hlk_sw16'

SIGNAL_AVAILABILITY = 'hlk_sw16_device_available'
SIGNAL_HANDLE_EVENT = 'hlk_sw16_handle_event_{}'

SWITCH_SCHEMA = vol.Schema({
    vol.Optional(CONF_NAME): cv.string,
})

RELAY_ID = vol.All(
    vol.Any(0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 'a', 'b', 'c', 'd', 'e', 'f'),
    vol.Coerce(str))

CONFIG_SCHEMA = vol.Schema({
    DOMAIN: vol.Schema({
        cv.string: vol.Schema({
            vol.Required(CONF_HOST): cv.string,
            vol.Optional(CONF_PORT, default=DEFAULT_PORT): cv.port,
            vol.Optional(CONF_RECONNECT_INTERVAL,
                         default=DEFAULT_RECONNECT_INTERVAL): int,
            vol.Required(CONF_SWITCHES): vol.Schema({RELAY_ID: SWITCH_SCHEMA}),
        }),
    }),
}, extra=vol.ALLOW_EXTRA)


async def async_setup(hass, config):
    """Set up the HLK-SW16 switch."""
    # Allow platform to specify function to register new unknown devices
    from hlk_sw16 import create_hlk_sw16_connection
    hass.data[DATA_DEVICE_REGISTER] = {}

    def add_device(device):
        switches = config[DOMAIN][device][CONF_SWITCHES]

        host = config[DOMAIN][device][CONF_HOST]
        port = config[DOMAIN][device][CONF_PORT]

        @callback
        def reconnect():
            """Schedule reconnect after connection has been lost."""
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
                reconnect_interval = config[DOMAIN][device][
                    CONF_RECONNECT_INTERVAL]
                _LOGGER.error(
                    "Error connecting to HLK-SW16, reconnecting in %s",
                    reconnect_interval)
                # Connection lost make entities unavailable
                async_dispatcher_send(hass, SIGNAL_AVAILABILITY, False)

                hass.loop.call_later(reconnect_interval, reconnect, exc)
                return

            hass.data[DATA_DEVICE_REGISTER][device] = protocol

            # Load platforms
            for comp_name, comp_conf in switches.items():
                hass.async_create_task(
                    async_load_platform(hass, 'switch', DOMAIN,
                                        (comp_name, comp_conf, device),
                                        config))

            # handle shutdown of HLK-SW16 asyncio transport
            hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STOP,
                                       lambda x: transport.close())

            _LOGGER.info('Connected to HLK-SW16')

        hass.async_create_task(connect())

    for device in config[DOMAIN]:
        add_device(device)
    return True


class SW16Device(Entity):
    """Representation of a HLK-SW16 device.

    Contains the common logic for HLK-SW16 entities.
    """

    def __init__(self, relay_name, device_port, device_id, protocol):
        """Initialize the device."""
        # HLK-SW16 specific attributes for every component type
        self._device_id = device_id
        self._device_port = device_port
        self._is_on = None
        self._protocol = protocol
        self._name = relay_name

    @callback
    def handle_event_callback(self, event):
        """Propagate changes through ha."""
        _LOGGER.debug("Relay %s new state callback: %r",
                      self._device_port, event)
        self._is_on = event
        self.async_schedule_update_ha_state()

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
        return bool(self._protocol)

    @callback
    def _availability_callback(self, availability):
        """Update availability state."""
        self.async_schedule_update_ha_state()

    async def async_added_to_hass(self):
        """Register update callback."""
        self._protocol.register_status_callback(self.handle_event_callback,
                                                self._device_port)
        self._is_on = await self._protocol.status(self._device_port)
        async_dispatcher_connect(self.hass, SIGNAL_AVAILABILITY,
                                 self._availability_callback)


class SwitchableSW16Device(SW16Device):
    """HLK-SW16 entity which can switch on/off (eg: light, switch)."""

    async def async_update(self):
        """Get current switch status from the device."""
        if not self.available:
            _LOGGER.error('Cannot send command, not connected!')
            return
        await self._protocol.status(self._device_port)

    async def async_turn_on(self, **kwargs):
        """Turn the device on."""
        if not self.available:
            _LOGGER.error('Cannot send command, not connected!')
            return
        await self._protocol.turn_on(self._device_port)

    async def async_turn_off(self, **kwargs):
        """Turn the device off."""
        if not self.available:
            _LOGGER.error('Cannot send command, not connected!')
            return
        await self._protocol.turn_off(self._device_port)
