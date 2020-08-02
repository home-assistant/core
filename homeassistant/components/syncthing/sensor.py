"""Support for monitoring the Syncthing instance."""

import logging

import aiosyncthing

from homeassistant.const import CONF_NAME
from homeassistant.exceptions import PlatformNotReady
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.event import async_track_time_interval

from .const import (
    DOMAIN,
    FOLDER_PAUSED_RECEIVED,
    FOLDER_SENSOR_ALERT_ICON,
    FOLDER_SENSOR_DEFAULT_ICON,
    FOLDER_SENSOR_ICONS,
    FOLDER_SUMMARY_RECEIVED,
    SCAN_INTERVAL,
    SERVER_AVAILABLE,
    SERVER_UNAVAILABLE,
    STATE_CHANGED_RECEIVED,
)

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass, config_entry, async_add_entities):
    """Set up the Syncthing sensors."""

    name = config_entry.data[CONF_NAME]
    synchting = hass.data[DOMAIN][name]

    try:
        config = await synchting.system.config()
        version = await synchting.system.version()
        dev = []

        for folder in config["folders"]:
            dev.append(FolderSensor(hass, synchting, name, folder, version["version"]))

        async_add_entities(dev)
    except aiosyncthing.exceptions.SyncthingError as exception:
        raise PlatformNotReady from exception


class FolderSensor(Entity):
    """A Syncthing folder sensor."""

    def __init__(self, hass, syncthing, name, folder, version):
        """Initialize the sensor."""
        self.hass = hass
        self._syncthing = syncthing
        self._name = name
        self._folder = folder
        self._state = None
        self._unsub_timer = None
        self._version = version

    @property
    def name(self):
        """Return the name of the sensor."""
        return f"{self._name} {self._folder['id']} {self._folder['label']}"

    @property
    def unique_id(self):
        """Return the unique id of the entity."""
        return f"{DOMAIN}-{self._name}-{self._folder['id']}"

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
        if self._state is None:
            return FOLDER_SENSOR_DEFAULT_ICON
        if self.state in FOLDER_SENSOR_ICONS:
            return FOLDER_SENSOR_ICONS[self.state]
        return FOLDER_SENSOR_ALERT_ICON

    @property
    def device_state_attributes(self):
        """Return the state attributes."""
        return self._state

    @property
    def should_poll(self):
        """Return the polling requirement for this sensor."""
        return False

    @property
    def device_info(self):
        """Return device information."""
        return {
            "identifiers": {(DOMAIN, self._name)},
            "name": self._name,
            "manufacturer": "Syncthing Team",
            "sw_version": self._version,
            "entry_type": "service",
        }

    async def async_update_status(self):
        """Request folder status and update state."""
        try:
            state = await self._syncthing.database.status(self._folder["id"])
            # A workaround, for some reason, state of paused folders is an empty string
            if state["state"] == "":
                state["state"] = "paused"
            self._state = state
        except aiosyncthing.exceptions.SyncthingError:
            self._state = None
        self.async_write_ha_state()

    def subscribe(self):
        """Start polling syncthing folder status."""
        if self._unsub_timer is None:

            async def refresh(event_time):
                """Get the latest data from Syncthing."""
                await self.async_update_status()

            self._unsub_timer = async_track_time_interval(
                self.hass, refresh, SCAN_INTERVAL
            )

    def unsubscribe(self):
        """Stop polling syncthing folder status."""
        if self._unsub_timer is not None:
            self._unsub_timer()
            self._unsub_timer = None

    async def async_added_to_hass(self):
        """Handle entity which will be added."""

        async def handle_folder_summary(event):
            if self._state is not None:
                # A workaround, for some reason, state of paused folder is an empty string
                if event["data"]["summary"]["state"] == "":
                    event["data"]["summary"]["state"] = "paused"
                self._state = event["data"]["summary"]
                self.async_write_ha_state()

        self.async_on_remove(
            async_dispatcher_connect(
                self.hass,
                f"{FOLDER_SUMMARY_RECEIVED}-{self._name}-{self._folder['id']}",
                handle_folder_summary,
            )
        )

        async def handle_state_chaged(event):
            if self._state is not None:
                self._state["state"] = event["data"]["to"]
                self.async_write_ha_state()

        self.async_on_remove(
            async_dispatcher_connect(
                self.hass,
                f"{STATE_CHANGED_RECEIVED}-{self._name}-{self._folder['id']}",
                handle_state_chaged,
            )
        )

        async def handle_folder_paused(event):
            if self._state is not None:
                self._state["state"] = "paused"
                self.async_write_ha_state()

        self.async_on_remove(
            async_dispatcher_connect(
                self.hass,
                f"{FOLDER_PAUSED_RECEIVED}-{self._name}-{self._folder['id']}",
                handle_folder_paused,
            )
        )

        async def handle_server_unavailable():
            self._state = None
            self.unsubscribe()
            self.async_write_ha_state()

        self.async_on_remove(
            async_dispatcher_connect(
                self.hass,
                f"{SERVER_UNAVAILABLE}-{self._name}",
                handle_server_unavailable,
            )
        )

        async def handle_server_available():
            self.subscribe()
            await self.async_update_status()

        self.async_on_remove(
            async_dispatcher_connect(
                self.hass, f"{SERVER_AVAILABLE}-{self._name}", handle_server_available,
            )
        )

        self.subscribe()
        self.async_on_remove(self.unsubscribe)

        await self.async_update_status()
