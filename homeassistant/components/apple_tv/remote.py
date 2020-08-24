"""Remote control support for Apple TV."""

import logging

from homeassistant.components import remote
from homeassistant.const import CONF_NAME
from homeassistant.core import callback

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

PARALLEL_UPDATES = 0


async def async_setup_entry(hass, config_entry, async_add_entities):
    """Load Apple TV remote based on a config entry."""
    name = config_entry.data[CONF_NAME]
    manager = hass.data[DOMAIN][config_entry.unique_id]
    async_add_entities([AppleTVRemote(name, config_entry.unique_id, manager)])


class AppleTVRemote(remote.RemoteEntity):
    """Device that sends commands to an Apple TV."""

    def __init__(self, name, identifier, manager):
        """Initialize device."""
        self.atv = None
        self._name = name
        self._identifier = identifier
        self._manager = manager

    async def async_added_to_hass(self):
        """Handle when an entity is about to be added to Home Assistant."""
        self._manager.listeners.append(self)

    async def async_will_remove_from_hass(self):
        """Handle when an entity is about to be removed from Home Assistant."""
        self._manager.listeners.remove(self)

    @callback
    def device_connected(self):
        """Handle when connection is made to device."""
        self.atv = self._manager.atv

    @callback
    def device_disconnected(self):
        """Handle when connection was lost to device."""
        self.atv = None

    @property
    def device_info(self):
        """Return the device info."""
        return {
            "identifiers": {(DOMAIN, self._identifier)},
            "manufacturer": "Apple",
            "name": self.name,
            "via_device": (DOMAIN, self._identifier),
        }

    @property
    def name(self):
        """Return the name of the device."""
        return self._name

    @property
    def unique_id(self):
        """Return a unique ID."""
        return self._identifier

    @property
    def is_on(self):
        """Return true if device is on."""
        return self.atv is not None

    @property
    def should_poll(self):
        """No polling needed for Apple TV."""
        return False

    async def async_turn_on(self, **kwargs):
        """Turn the device on."""
        await self._manager.connect()

    async def async_turn_off(self, **kwargs):
        """Turn the device off."""
        await self._manager.disconnect()

    async def async_send_command(self, command, **kwargs):
        """Send a command to one device."""
        if not self.is_on:
            _LOGGER.error("Unable to send commands, not connected to %s", self._name)
            return

        for single_command in command:
            if not hasattr(self.atv.remote_control, single_command):
                continue

            await getattr(self.atv.remote_control, single_command)()
