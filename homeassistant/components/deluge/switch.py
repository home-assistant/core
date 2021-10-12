"""Support for setting the Deluge BitTorrent client in Pause."""
import logging

from homeassistant.const import CONF_NAME, STATE_OFF, STATE_ON
from homeassistant.core import callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity import ToggleEntity

from . import DelugeClient
from .const import DOMAIN

_LOGGING = logging.getLogger(__name__)


async def async_setup_entry(hass, config_entry, async_add_entities):
    """Set up the Deluge switch."""

    deluge_client = hass.data[DOMAIN][config_entry.entry_id]
    name = config_entry.data[CONF_NAME]

    entities = [
        DelugeSwitch("Switch", deluge_client, name),
    ]

    async_add_entities(entities, True)


class DelugeSwitch(ToggleEntity):
    """Representation of a Deluge switch."""

    def __init__(self, switch_name, deluge_client, name):
        """Initialize the Deluge switch."""
        self._name = switch_name
        self._deluge_client: DelugeClient = deluge_client
        self.client_name = name
        self._state = STATE_OFF
        self.unsub_update = None

    @property
    def name(self):
        """Return the name of the switch."""
        return f"{self.client_name} {self._name}"

    @property
    def unique_id(self):
        """Return the unique id of the entity."""
        return f"{self._deluge_client.state.host}-{self.name}"

    @property
    def should_poll(self) -> bool:
        """Poll for status regularly."""
        return False

    @property
    def is_on(self) -> bool:
        """Return True if entity is on."""
        return self._state == STATE_ON

    @property
    def available(self):
        """Could the device be accessed during the last update call."""
        return self._deluge_client.state.available

    def turn_on(self, **kwargs):
        """Turn the device on."""
        _LOGGING.debug("Starting all torrents")
        self._deluge_client.state.resume_torrents()
        self._deluge_client.state.update()

    def turn_off(self, **kwargs):
        """Turn the device off."""
        _LOGGING.debug("Stopping all torrents")
        self._deluge_client.state.pause_torrents()
        self._deluge_client.state.update()

    async def async_added_to_hass(self):
        """Handle entity which will be added."""
        self.unsub_update = async_dispatcher_connect(
            self.hass,
            self._deluge_client.state.signal_update,
            self._schedule_immediate_update,
        )

    @callback
    def _schedule_immediate_update(self):
        self.async_schedule_update_ha_state(True)

    async def will_remove_from_hass(self):
        """Unsubscribe from update dispatcher."""
        if self.unsub_update:
            self.unsub_update()
            self.unsub_update = None

    def update(self):
        """Get the latest data from Deluge and updates the state."""
        torrents = self._deluge_client.state.torrents
        if not torrents:
            return

        all_torrents_paused = all(torrent[b"state"] == "paused" for torrent in torrents)
        self._state = STATE_OFF if all_torrents_paused else STATE_ON
