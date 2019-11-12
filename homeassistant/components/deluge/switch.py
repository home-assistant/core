"""Support for setting the Deluge BitTorrent client in Pause."""
import logging

from homeassistant.const import CONF_NAME, STATE_OFF, STATE_ON
from homeassistant.core import callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity import ToggleEntity

from .const import DELUGE_SWITCH, DOMAIN

_LOGGER = logging.getLogger(__name__)


async def setup_platform(hass, config, add_entities, discovery_info=None):
    """Import config from configuration.yaml."""
    pass


async def async_setup_entry(hass, config_entry, async_add_entities):
    """Set up Deluge switch."""

    client = hass.data[DOMAIN][config_entry.entry_id]
    name = config_entry.data[CONF_NAME]

    async_add_entities([DelugeSwitch(client, name)])


class DelugeSwitch(ToggleEntity):
    """Representation of a Deluge switch."""

    def __init__(self, client, name):
        """Initialize the Deluge switch."""
        self._name = name
        self.client = client
        self._state = STATE_OFF
        self._available = False
        self.unsub_dispatcher = None

    @property
    def name(self):
        """Return the name of the switch."""
        return f"{self._name} {DELUGE_SWITCH}"

    @property
    def unique_id(self):
        """Return the unique id of the entity."""
        return f"{self.client.api.host}-{self.name}"

    @property
    def state(self):
        """Return the state of the device."""
        return self._state

    @property
    def should_poll(self):
        """Poll for status regularly."""
        return False

    @property
    def is_on(self):
        """Return true if device is on."""
        return self._state == STATE_ON

    @property
    def available(self):
        """Return true if device is available."""
        return self.client.api.available

    def turn_on(self, **kwargs):
        """Start all torrents."""
        _LOGGER.debug("Starting all torrents")
        self.client.api.start_torrents()
        self.client.api.update()

    def turn_off(self, **kwargs):
        """Stop all torrents."""
        _LOGGER.debug("Stoping all torrents")
        self.client.api.stop_torrents()
        self.client.api.update()

    async def async_added_to_hass(self):
        """Handle entity which will be added."""
        self.unsub_dispatcher = async_dispatcher_connect(
            self.hass, self.client.api.signal_update, self._schedule_immediate_update,
        )

    @callback
    def _schedule_immediate_update(self):
        self.async_schedule_update_ha_state(True)

    def update(self):
        """Get the latest data from deluge and updates the state."""
        if self.client.api.get_active_torrents_count() > 0:
            self._state = STATE_ON
        else:
            self._state = STATE_OFF

    async def will_remove_from_hass(self):
        """Unsub from update dispatcher."""
        if self.unsub_dispatcher:
            self.unsub_dispatcher()
