"""Support for monitoring the Syncthing instance."""

import logging

import syncthing

from homeassistant.const import CONF_NAME
from homeassistant.core import callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity import Entity

from .const import (
    DOMAIN,
    FOLDER_PAUSED_RECEIVED,
    FOLDER_SUMMARY_RECEIVED,
    STATE_CHANGED_RECEIVED,
)

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

    @property
    def should_poll(self):
        """Return the polling requirement for this sensor."""
        return False

    async def async_update(self):
        """Update device state."""

        if self._state is not None:
            return

        try:
            _LOGGER.info(f"Folder {self._folder['id']} is updating...")
            state = await self._hass.async_add_executor_job(
                self._client.database.status, self._folder["id"]
            )
            # A workaround, for some reason, state of paused folder is an empty string
            if state["state"] == "":
                state["state"] = "paused"
            self._state = state
        except syncthing.SyncthingError:
            self._state = None

    async def async_added_to_hass(self):
        """Handle entity which will be added."""

        @callback
        def handle_folder_summary(event):
            """Update the state."""
            if self._state is not None:
                # A workaround, for some reason, state of paused folder is an empty string
                if event["data"]["summary"]["state"] == "":
                    event["data"]["summary"]["state"] = "paused"
                self._state = event["data"]["summary"]
                self.async_schedule_update_ha_state(True)
            pass

        self.async_on_remove(
            async_dispatcher_connect(
                self.hass,
                f"{FOLDER_SUMMARY_RECEIVED}-{self._client_name}-{self._folder['id']}",
                handle_folder_summary,
            )
        )

        @callback
        def handle_state_chaged(event):
            """Update the state."""
            if self._state is not None:
                self._state["state"] = event["data"]["to"]
                self.async_schedule_update_ha_state(True)

        self.async_on_remove(
            async_dispatcher_connect(
                self.hass,
                f"{STATE_CHANGED_RECEIVED}-{self._client_name}-{self._folder['id']}",
                handle_state_chaged,
            )
        )

        @callback
        def handle_folder_paused(event):
            """Update the state."""
            if self._state is not None:
                self._state["state"] = "paused"
                self.async_schedule_update_ha_state(True)

        self.async_on_remove(
            async_dispatcher_connect(
                self.hass,
                f"{FOLDER_PAUSED_RECEIVED}-{self._client_name}-{self._folder['id']}",
                handle_folder_paused,
            )
        )
