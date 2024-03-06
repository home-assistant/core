"""Support for HLK-SW16 relay switches."""
import logging

from hlk_sw16 import create_hlk_sw16_connection
import voluptuous as vol

from homeassistant.config_entries import SOURCE_IMPORT, ConfigEntry
from homeassistant.const import CONF_HOST, CONF_NAME, CONF_PORT, CONF_SWITCHES, Platform
from homeassistant.core import HomeAssistant, callback
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.dispatcher import (
    async_dispatcher_connect,
    async_dispatcher_send,
)
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.typing import ConfigType

from .const import (
    CONNECTION_TIMEOUT,
    DEFAULT_KEEP_ALIVE_INTERVAL,
    DEFAULT_PORT,
    DEFAULT_RECONNECT_INTERVAL,
    DOMAIN,
)

_LOGGER = logging.getLogger(__name__)

PLATFORMS = [Platform.SWITCH]

DATA_DEVICE_REGISTER = "hlk_sw16_device_register"
DATA_DEVICE_LISTENER = "hlk_sw16_device_listener"

SWITCH_SCHEMA = vol.Schema({vol.Optional(CONF_NAME): cv.string})

RELAY_ID = vol.All(
    vol.Any(0, 1, 2, 3, 4, 5, 6, 7, 8, 9, "a", "b", "c", "d", "e", "f"), vol.Coerce(str)
)

CONFIG_SCHEMA = vol.Schema(
    {
        DOMAIN: vol.Schema(
            {
                cv.string: vol.Schema(
                    {
                        vol.Required(CONF_HOST): cv.string,
                        vol.Optional(CONF_PORT, default=DEFAULT_PORT): cv.port,
                        vol.Required(CONF_SWITCHES): vol.Schema(
                            {RELAY_ID: SWITCH_SCHEMA}
                        ),
                    }
                )
            }
        )
    },
    extra=vol.ALLOW_EXTRA,
)


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Component setup, do nothing."""
    if DOMAIN not in config:
        return True

    for device_id in config[DOMAIN]:
        conf = config[DOMAIN][device_id]
        hass.async_create_task(
            hass.config_entries.flow.async_init(
                DOMAIN,
                context={"source": SOURCE_IMPORT},
                data={CONF_HOST: conf[CONF_HOST], CONF_PORT: conf[CONF_PORT]},
            )
        )
    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up the HLK-SW16 switch."""
    hass.data.setdefault(DOMAIN, {})
    host = entry.data[CONF_HOST]
    port = entry.data[CONF_PORT]
    address = f"{host}:{port}"

    hass.data[DOMAIN][entry.entry_id] = {}

    @callback
    def disconnected():
        """Schedule reconnect after connection has been lost."""
        _LOGGER.warning("HLK-SW16 %s disconnected", address)
        async_dispatcher_send(
            hass, f"hlk_sw16_device_available_{entry.entry_id}", False
        )

    @callback
    def reconnected():
        """Schedule reconnect after connection has been lost."""
        _LOGGER.warning("HLK-SW16 %s connected", address)
        async_dispatcher_send(hass, f"hlk_sw16_device_available_{entry.entry_id}", True)

    _LOGGER.debug("Initiating HLK-SW16 connection to %s", address)

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
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    _LOGGER.debug("Connected to HLK-SW16 device: %s", address)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    client = hass.data[DOMAIN][entry.entry_id].pop(DATA_DEVICE_REGISTER)
    client.stop()
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        if hass.data[DOMAIN][entry.entry_id]:
            hass.data[DOMAIN].pop(entry.entry_id)
        if not hass.data[DOMAIN]:
            hass.data.pop(DOMAIN)
    return unload_ok


class SW16Device(Entity):
    """Representation of a HLK-SW16 device.

    Contains the common logic for HLK-SW16 entities.
    """

    _attr_should_poll = False

    def __init__(self, device_port, entry_id, client):
        """Initialize the device."""
        # HLK-SW16 specific attributes for every component type
        self._entry_id = entry_id
        self._device_port = device_port
        self._is_on = None
        self._client = client
        self._attr_name = device_port
        self._attr_unique_id = f"{self._entry_id}_{self._device_port}"

    @callback
    def handle_event_callback(self, event):
        """Propagate changes through ha."""
        _LOGGER.debug("Relay %s new state callback: %r", self.unique_id, event)
        self._is_on = event
        self.async_write_ha_state()

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
