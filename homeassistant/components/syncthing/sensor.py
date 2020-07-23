"""Support for monitoring the Syncthing instance."""

import logging

import syncthing

from homeassistant.const import CONF_NAME
from homeassistant.helpers.entity import Entity

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass, config_entry, async_add_entities):
    """Set up the Syncthing sensors."""

    client = hass.data[DOMAIN][config_entry.entry_id]["client"]
    name = config_entry.data[CONF_NAME]

    config = await hass.async_add_executor_job(client.system.config)

    dev = []

    for folder in config["folders"]:
        dev.append(FolderSensor(hass, client, name, folder))

    async_add_entities(dev, True)


class FolderSensor(Entity):
    """A Syncthing folder sensor."""

    def __init__(self, hass, client, client_name, folder):
        """Initialize the sensor."""
        self._hass = hass
        self._client = client
        self._client_name = client_name
        self._folder = folder
        self._state = None

    @property
    def name(self):
        """Return the name of the sensor."""
        return (
            f"{DOMAIN} {self._client_name} {self._folder['id']} {self._folder['label']}"
        )

    @property
    def unique_id(self):
        """Return the unique id of the entity."""
        return f"{DOMAIN}-{self._client_name}-{self._folder['id']}"

    @property
    def state(self):
        """Return the state of the sensor."""
        return self._state["state"]

    @property
    def available(self):
        """Could the device be accessed during the last update call."""
        return self._state is not None

    @property
    def icon(self):
        """Return the icon for this sensor."""
        return "mdi:folder"

    @property
    def device_state_attributes(self):
        """Return the state attributes."""
        return self._state

    async def async_update(self):
        """Update device state."""
        try:
            self._state = await self._hass.async_add_executor_job(
                self._client.database.status, self._folder["id"]
            )
        except syncthing.SyncthingError:
            self._state = None
