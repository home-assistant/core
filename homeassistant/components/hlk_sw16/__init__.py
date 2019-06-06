"""Support for HLK-SW16 relay switches."""
import logging

import voluptuous as vol

from homeassistant.const import (
    CONF_HOST, CONF_PORT,
    EVENT_HOMEASSISTANT_STOP, CONF_SWITCHES, CONF_NAME)
from homeassistant.core import callback
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.discovery import async_load_platform
from homeassistant.helpers.dispatcher import (
    async_dispatcher_send, async_dispatcher_connect)

_LOGGER = logging.getLogger(__name__)

DATA_DEVICE_REGISTER = 'hlk_sw16_device_register'
DEFAULT_RECONNECT_INTERVAL = 10
CONNECTION_TIMEOUT = 10
DEFAULT_PORT = 8080

DOMAIN = 'hlk_sw16'

SIGNAL_AVAILABILITY = 'hlk_sw16_device_available_{}'

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
        def disconnected():
            """Schedule reconnect after connection has been lost."""
            _LOGGER.warning('HLK-SW16 %s disconnected', device)
            async_dispatcher_send(hass, SIGNAL_AVAILABILITY.format(device),
                                  False)

        @callback
        def reconnected():
            """Schedule reconnect after connection has been lost."""
            _LOGGER.warning('HLK-SW16 %s connected', device)
            async_dispatcher_send(hass, SIGNAL_AVAILABILITY.format(device),
                                  True)

        async def connect():
            """Set up connection and hook it into HA for reconnect/shutdown."""
            _LOGGER.info('Initiating HLK-SW16 connection to %s', device)

            client = await create_hlk_sw16_connection(
                host=host,
                port=port,
                disconnect_callback=disconnected,
                reconnect_callback=reconnected,
                loop=hass.loop,
                timeout=CONNECTION_TIMEOUT,
                reconnect_interval=DEFAULT_RECONNECT_INTERVAL)

            hass.data[DATA_DEVICE_REGISTER][device] = client

            # Load platforms
            hass.async_create_task(
                async_load_platform(hass, 'switch', DOMAIN,
                                    (switches, device),
                                    config))

            # handle shutdown of HLK-SW16 asyncio transport
            hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STOP,
                                       lambda x: client.stop())

            _LOGGER.info('Connected to HLK-SW16 device: %s', device)

        hass.loop.create_task(connect())

    for device in config[DOMAIN]:
        add_device(device)
    return True


class SW16Device(Entity):
    """Representation of a HLK-SW16 device.

    Contains the common logic for HLK-SW16 entities.
    """

    def __init__(self, relay_name, device_port, device_id, client):
        """Initialize the device."""
        # HLK-SW16 specific attributes for every component type
        self._device_id = device_id
        self._device_port = device_port
        self._is_on = None
        self._client = client
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
    def available(self):
        """Return True if entity is available."""
        return bool(self._client.is_connected)

    @callback
    def _availability_callback(self, availability):
        """Update availability state."""
        self.async_schedule_update_ha_state()

    async def async_added_to_hass(self):
        """Register update callback."""
        self._client.register_status_callback(self.handle_event_callback,
                                              self._device_port)
        self._is_on = await self._client.status(self._device_port)
        async_dispatcher_connect(self.hass,
                                 SIGNAL_AVAILABILITY.format(self._device_id),
                                 self._availability_callback)
