"""Support for HLK-SW16 relay switches."""
import logging

from hlk_sw16 import create_hlk_sw16_connection

from homeassistant.const import CONF_HOST, CONF_NAME, CONF_PORT
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
    DOMAIN,
)

_LOGGER = logging.getLogger(__name__)

DATA_DEVICE_REGISTER = "hlk_sw16_device_register"
DATA_DEVICE_LISTENER = "hlk_sw16_device_listener"


async def async_setup(hass, config):
    """Component setup, do nothing."""
    hass.data.setdefault(DOMAIN, {})
    return True


async def async_setup_entry(hass, entry):
    """Set up the HLK-SW16 switch."""
    # Allow platform to specify function to register new unknown devices

    if hass.data.get(DATA_DEVICE_REGISTER, None) is None:
        hass.data[DATA_DEVICE_REGISTER] = {}
    if hass.data.get(DATA_DEVICE_LISTENER, None) is None:
        hass.data[DATA_DEVICE_LISTENER] = {}
    device = entry.data[CONF_NAME]
    host = entry.data[CONF_HOST]
    port = entry.data[CONF_PORT]

    hass.data[DOMAIN][entry.entry_id] = {}

    @callback
    def disconnected():
        """Schedule reconnect after connection has been lost."""
        _LOGGER.warning("HLK-SW16 %s disconnected", device)
        async_dispatcher_send(
            hass, f"hlk_sw16_device_available_{entry.entry_id}", False
        )

    @callback
    def reconnected():
        """Schedule reconnect after connection has been lost."""
        _LOGGER.warning("HLK-SW16 %s connected", device)
        async_dispatcher_send(hass, f"hlk_sw16_device_available_{entry.entry_id}", True)

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

        hass.data[DOMAIN][entry.entry_id][DATA_DEVICE_REGISTER] = client

        # Load entities
        hass.async_create_task(
            hass.config_entries.async_forward_entry_setup(entry, "switch")
        )

        _LOGGER.info("Connected to HLK-SW16 device: %s", device)

    hass.loop.create_task(connect())

    return True


async def async_unload_entry(hass, entry):
    """Unload a config entry."""
    client = hass.data[DOMAIN][entry.entry_id].pop(DATA_DEVICE_REGISTER)
    client.stop()
    return await hass.config_entries.async_forward_entry_unload(entry, "switch")


async def async_remove_entry(hass, entry):
    """Stop client config entry."""
    if hass.data[DOMAIN][entry.entry_id]:
        hass.data[DOMAIN].pop(entry.entry_id)
    if not hass.data[DOMAIN]:
        hass.data.pop(DOMAIN)


class SW16Device(Entity):
    """Representation of a HLK-SW16 device.

    Contains the common logic for HLK-SW16 entities.
    """

    def __init__(self, device_port, entry_id, client):
        """Initialize the device."""
        # HLK-SW16 specific attributes for every component type
        self._entry_id = entry_id
        self._device_port = device_port
        self._is_on = None
        self._client = client
        self._name = device_port

    @property
    def unique_id(self):
        """Return a unique ID."""
        return f"{self._entry_id}_{self._device_port}"

    @callback
    def handle_event_callback(self, event):
        """Propagate changes through ha."""
        _LOGGER.debug("Relay %s new state callback: %r", self.unique_id, event)
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
                f"hlk_sw16_device_available_{self._entry_id}",
                self._availability_callback,
            )
        )
