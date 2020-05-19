"""Support for HLK-SW16 relay switches."""
import logging

from hlk_sw16 import create_hlk_sw16_connection

from homeassistant.const import (
    CONF_HOST,
    CONF_NAME,
    CONF_PORT,
    EVENT_HOMEASSISTANT_STOP,
)
from homeassistant.core import callback
from homeassistant.helpers.dispatcher import (
    async_dispatcher_connect,
    async_dispatcher_send,
)
from homeassistant.helpers.entity import Entity

from .const import (
    CONNECTION_TIMEOUT,
    DEFAULT_KEEP_ALIVE_INTERVAL,
    DEFAULT_RECONNECT_INTERVAL,
)

_LOGGER = logging.getLogger(__name__)

DATA_DEVICE_REGISTER = "hlk_sw16_device_register"
DATA_DEVICE_LISTENER = "hlk_sw16_device_listener"


async def async_setup(hass, config):
    """Component setup, do nothing."""
    return True


async def async_setup_entry(hass, entry):
    """Set up the HLK-SW16 switch."""
    # Allow platform to specify function to register new unknown devices

    if hass.data.get(DATA_DEVICE_REGISTER, None) is None:
        hass.data[DATA_DEVICE_REGISTER] = {}
    if hass.data.get(DATA_DEVICE_LISTENER, None) is None:
        hass.data[DATA_DEVICE_LISTENER] = {}
    address = f"{entry.data[CONF_HOST]}:{entry.data[CONF_PORT]}"
    device = entry.data[CONF_NAME]
    host = entry.data[CONF_HOST]
    port = entry.data[CONF_PORT]

    @callback
    def disconnected():
        """Schedule reconnect after connection has been lost."""
        _LOGGER.warning("HLK-SW16 %s disconnected", device)
        async_dispatcher_send(hass, f"hlk_sw16_device_available_{address}", False)

    @callback
    def reconnected():
        """Schedule reconnect after connection has been lost."""
        _LOGGER.warning("HLK-SW16 %s connected", device)
        async_dispatcher_send(hass, f"hlk_sw16_device_available_{address}", True)

    async def connect():
        """Set up connection and hook it into HA for reconnect/shutdown."""
        _LOGGER.info("Initiating HLK-SW16 connection to %s", device)

        client = await create_hlk_sw16_connection(
            host=host,
            port=port,
            disconnect_callback=disconnected,
            reconnect_callback=reconnected,
            loop=hass.loop,
            timeout=CONNECTION_TIMEOUT,
            reconnect_interval=DEFAULT_RECONNECT_INTERVAL,
            keep_alive_interval=DEFAULT_KEEP_ALIVE_INTERVAL,
        )

        hass.data[DATA_DEVICE_REGISTER][address] = client

        # Load entities
        hass.async_create_task(
            hass.config_entries.async_forward_entry_setup(entry, "switch")
        )

        # handle shutdown of HLK-SW16 asyncio transport
        hass.data[DATA_DEVICE_LISTENER][address] = hass.bus.async_listen_once(
            EVENT_HOMEASSISTANT_STOP, lambda x: client.stop()
        )

        _LOGGER.info("Connected to HLK-SW16 device: %s", device)

    hass.loop.create_task(connect())

    return True


async def async_unload_entry(hass, entry):
    """Unload a config entry."""
    return await hass.config_entries.async_forward_entry_unload(entry, "switch")


async def async_remove_entry(hass, entry):
    """Stop client config entry."""
    address = f"{entry.data[CONF_HOST]}:{entry.data[CONF_PORT]}"
    client = hass.data[DATA_DEVICE_REGISTER].pop(address)
    client.stop()
    if not hass.data[DATA_DEVICE_REGISTER]:
        hass.data.pop(DATA_DEVICE_REGISTER)
    remove_listener = hass.data[DATA_DEVICE_LISTENER].pop(address)
    remove_listener()
    if not hass.data[DATA_DEVICE_LISTENER]:
        hass.data.pop(DATA_DEVICE_LISTENER)


class SW16Device(Entity):
    """Representation of a HLK-SW16 device.

    Contains the common logic for HLK-SW16 entities.
    """

    def __init__(self, device_port, address, client):
        """Initialize the device."""
        # HLK-SW16 specific attributes for every component type
        self._address = address
        self._device_port = device_port
        self._is_on = None
        self._client = client
        self._name = device_port

    @property
    def unique_id(self):
        """Return a unique ID."""
        return f"{self._address}:{self._device_port}"

    @callback
    def handle_event_callback(self, event):
        """Propagate changes through ha."""
        _LOGGER.debug("Relay %s new state callback: %r", self._device_port, event)
        self._is_on = event
        self.async_write_ha_state()

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
        self.async_write_ha_state()

    async def async_added_to_hass(self):
        """Register update callback."""
        self._client.register_status_callback(
            self.handle_event_callback, self._device_port
        )
        self._is_on = await self._client.status(self._device_port)
        self.async_on_remove(
            async_dispatcher_connect(
                self.hass,
                f"hlk_sw16_device_available_{self._address}",
                self._availability_callback,
            )
        )
