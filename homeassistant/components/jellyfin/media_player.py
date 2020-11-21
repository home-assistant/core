import logging

from jellyfin_apiclient_python.client import JellyfinClient


from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from homeassistant.components.media_player import PLATFORM_SCHEMA, MediaPlayerEntity

from .const import DATA_CLIENT, DOMAIN  # pylint:disable=unused-import

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities
):
    """Setup a Jellyfin connection from a config entry"""

    data = hass.data[DOMAIN][entry.entry_id]
    client = data[DATA_CLIENT]

    uid = entry.unique_id
    if uid is None:
        uid = entry.entry_id

    entity = JellyfinEntity(client, uid)
    async_add_entities([entity])


class JellyfinEntity(MediaPlayerEntity):
    """Represents a Jellyfin server"""

    def __init__(self, client: JellyfinClient, uid: str):
        self.client = client
        self.api = client.jellyfin
        self._unique_id = uid

        server_id = client.auth.server_id
        self._name = client.auth.get_server_info(server_id)["Name"]

    @property
    def name(self):
        """Return the name of the device."""
        return self._name

    @property
    def unique_id(self):
        """Return the unique id of the device."""
        return self._unique_id

    @property
    def state(self):
        """State of the player."""
        return None