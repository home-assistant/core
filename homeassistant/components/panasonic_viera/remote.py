"""Remote control support for Panasonic Viera TV."""
import logging

from homeassistant.components.remote import RemoteEntity
from homeassistant.const import CONF_NAME, STATE_ON

from .const import ATTR_REMOTE, DOMAIN

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass, config_entry, async_add_entities):
    """Set up Panasonic Viera TV Remote from a config entry."""

    config = config_entry.data

    remote = hass.data[DOMAIN][config_entry.entry_id][ATTR_REMOTE]
    name = config[CONF_NAME]

    remote_device = PanasonicVieraRemoteEntity(remote, name)
    async_add_entities([remote_device])


class PanasonicVieraRemoteEntity(RemoteEntity):
    """Representation of a Panasonic Viera TV Remote."""

    def __init__(self, remote, name, uuid=None):
        """Initialize the entity."""
        # Save a reference to the imported class
        self._remote = remote
        self._name = name
        self._uuid = uuid

    @property
    def unique_id(self):
        """Return the unique ID of the device."""
        return self._uuid

    @property
    def name(self):
        """Return the name of the device."""
        return self._name

    @property
    def available(self):
        """Return True if the device is available."""
        return self._remote.available

    @property
    def is_on(self):
        """Return true if device is on."""
        return self._remote.state == STATE_ON

    async def async_turn_on(self, **kwargs):
        """Turn the device on."""
        await self._remote.async_turn_on()

    async def async_turn_off(self, **kwargs):
        """Turn the device off."""
        await self._remote.async_turn_off()

    async def async_send_command(self, command, **kwargs):
        """Send a command to one device."""
        for cmd in command:
            await self._remote.async_send_key(cmd)
