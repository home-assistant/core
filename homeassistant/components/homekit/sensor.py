"""Support for homekit sensors."""
import logging

from homeassistant.core import callback

from .const import DOMAIN, HOMEKIT
from .entity import HomeKitEntity
from .type_media_players import TelevisionMediaPlayer

_LOGGER = logging.getLogger(__name__)

HOMEKIT_REMOTE_MODEL = "HomeKit Remote"


async def async_setup_entry(hass, config_entry, async_add_entities):
    """Set up the homekit sensors."""

    homekit = hass.data[DOMAIN][config_entry.entry_id][HOMEKIT]
    mac = homekit.driver.state.mac
    entities = []

    for acc in homekit.bridge.accessories.values():
        if isinstance(acc, TelevisionMediaPlayer):
            entities.append(RemoteKeySensor(mac, acc))

    async_add_entities(entities, False)


class RemoteKeySensor(HomeKitEntity):
    """Representation of an homekit remote control sensor."""

    def __init__(self, mac, acc):
        """Init the remote control sensor."""
        super().__init__(mac, acc, HOMEKIT_REMOTE_MODEL)
        self._state = None

    @property
    def name(self):
        """Sensor Name."""
        return f"{self.acc.name} {self.model}"

    @property
    def unique_id(self):
        """Sensor Uniqueid."""
        return f"{self.base_unique_id}_remote"

    @property
    def state(self):
        """Key pressed."""
        return self._state

    @callback
    def _async_key_pressed(self, value):
        """Update the sensor with the keypress."""
        # Press
        self._state = value
        self.async_write_ha_state()
        # .. and release
        self._state = None
        self.async_write_ha_state()

    async def async_added_to_hass(self):
        """Subscribe to updates."""
        self.async_on_remove(
            self.acc.async_add_remote_key_listener(self._async_key_pressed)
        )
