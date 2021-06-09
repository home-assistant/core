"""Support for monitoring the Syncthing instance."""

import logging
from time import monotonic

import aiosyncthing

from homeassistant.components.sensor import SensorEntity
from homeassistant.const import DATA_RATE_MEGABYTES_PER_SECOND
from homeassistant.core import callback
from homeassistant.exceptions import PlatformNotReady
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.event import async_track_time_interval
from homeassistant.helpers.update_coordinator import (
    CoordinatorEntity,
    DataUpdateCoordinator,
    UpdateFailed,
)

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
    SPEED_SCAN_INTERVAL,
    STATE_CHANGED_RECEIVED,
)

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass, config_entry, async_add_entities):
    """Set up the Syncthing sensors."""
    syncthing = hass.data[DOMAIN][config_entry.entry_id]

    try:
        config = await syncthing.system.config()
        version = await syncthing.system.version()
    except aiosyncthing.exceptions.SyncthingError as exception:
        raise PlatformNotReady from exception

    server_id = syncthing.server_id
    folder_entities = [
        FolderSensor(
            syncthing,
            server_id,
            folder["id"],
            folder["label"],
            version["version"],
        )
        for folder in config["folders"]
    ]

    async def async_update_data():
        try:
            return await syncthing.system.connections()
        except aiosyncthing.exceptions.SyncthingError as err:
            raise UpdateFailed from err

    coordinator = DataUpdateCoordinator(
        hass,
        _LOGGER,
        name="sensor",
        update_method=async_update_data,
        update_interval=SPEED_SCAN_INTERVAL,
    )
    await coordinator.async_refresh()

    speed_entities = [
        SpeedSensor(
            coordinator, syncthing.url, server_id, "download", version["version"]
        ),
        SpeedSensor(
            coordinator, syncthing.url, server_id, "upload", version["version"]
        ),
    ]

    async_add_entities(folder_entities + speed_entities)


class FolderSensor(SensorEntity):
    """A Syncthing folder sensor."""

    _attr_should_poll = False

    STATE_ATTRIBUTES = {
        "errors": "errors",
        "globalBytes": "global_bytes",
        "globalDeleted": "global_deleted",
        "globalDirectories": "global_directories",
        "globalFiles": "global_files",
        "globalSymlinks": "global_symlinks",
        "globalTotalItems": "global_total_items",
        "ignorePatterns": "ignore_patterns",
        "inSyncBytes": "in_sync_bytes",
        "inSyncFiles": "in_sync_files",
        "invalid": "invalid",
        "localBytes": "local_bytes",
        "localDeleted": "local_deleted",
        "localDirectories": "local_directories",
        "localFiles": "local_files",
        "localSymlinks": "local_symlinks",
        "localTotalItems": "local_total_items",
        "needBytes": "need_bytes",
        "needDeletes": "need_deletes",
        "needDirectories": "need_directories",
        "needFiles": "need_files",
        "needSymlinks": "need_symlinks",
        "needTotalItems": "need_total_items",
        "pullErrors": "pull_errors",
        "state": "state",
    }

    def __init__(self, syncthing, server_id, folder_id, folder_label, version):
        """Initialize the sensor."""
        self._syncthing = syncthing
        self._server_id = server_id
        self._folder_id = folder_id
        self._folder_label = folder_label
        self._state = None
        self._unsub_timer = None
        self._version = version

        self._short_server_id = server_id.split("-")[0]

        self._attr_name = (
            f"{self._short_server_id} {self._folder_id} {self._folder_label}"
        )
        self._attr_unique_id = f"{self._short_server_id}-{self._folder_id}"
        self._attr_device_info = {
            "identifiers": {(DOMAIN, self._server_id)},
            "name": f"Syncthing ({self._syncthing.url})",
            "manufacturer": "Syncthing Team",
            "sw_version": self._version,
            "entry_type": "service",
        }

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
    def extra_state_attributes(self):
        """Return the state attributes."""
        return self._state

    async def async_update_status(self):
        """Request folder status and update state."""
        try:
            state = await self._syncthing.database.status(self._folder_id)
        except aiosyncthing.exceptions.SyncthingError:
            self._state = None
        else:
            self._state = self._filter_state(state)
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

    @callback
    def unsubscribe(self):
        """Stop polling syncthing folder status."""
        if self._unsub_timer is not None:
            self._unsub_timer()
            self._unsub_timer = None

    async def async_added_to_hass(self):
        """Handle entity which will be added."""

        @callback
        def handle_folder_summary(event):
            if self._state is not None:
                self._state = self._filter_state(event["data"]["summary"])
                self.async_write_ha_state()

        self.async_on_remove(
            async_dispatcher_connect(
                self.hass,
                f"{FOLDER_SUMMARY_RECEIVED}-{self._server_id}-{self._folder_id}",
                handle_folder_summary,
            )
        )

        @callback
        def handle_state_changed(event):
            if self._state is not None:
                self._state["state"] = event["data"]["to"]
                self.async_write_ha_state()

        self.async_on_remove(
            async_dispatcher_connect(
                self.hass,
                f"{STATE_CHANGED_RECEIVED}-{self._server_id}-{self._folder_id}",
                handle_state_changed,
            )
        )

        @callback
        def handle_folder_paused(event):
            if self._state is not None:
                self._state["state"] = "paused"
                self.async_write_ha_state()

        self.async_on_remove(
            async_dispatcher_connect(
                self.hass,
                f"{FOLDER_PAUSED_RECEIVED}-{self._server_id}-{self._folder_id}",
                handle_folder_paused,
            )
        )

        @callback
        def handle_server_unavailable():
            self._state = None
            self.unsubscribe()
            self.async_write_ha_state()

        self.async_on_remove(
            async_dispatcher_connect(
                self.hass,
                f"{SERVER_UNAVAILABLE}-{self._server_id}",
                handle_server_unavailable,
            )
        )

        async def handle_server_available():
            self.subscribe()
            await self.async_update_status()

        self.async_on_remove(
            async_dispatcher_connect(
                self.hass,
                f"{SERVER_AVAILABLE}-{self._server_id}",
                handle_server_available,
            )
        )

        self.subscribe()
        self.async_on_remove(self.unsubscribe)

        await self.async_update_status()

    def _filter_state(self, state):
        # Select only needed state attributes and map their names
        state = {
            self.STATE_ATTRIBUTES[key]: value
            for key, value in state.items()
            if key in self.STATE_ATTRIBUTES
        }

        # A workaround, for some reason, state of paused folders is an empty string
        if state["state"] == "":
            state["state"] = "paused"

        # Add some useful attributes
        state["id"] = self._folder_id
        state["label"] = self._folder_label

        return state


class SpeedSensor(CoordinatorEntity):
    """A syncthing speed sensor."""

    NAMES = {"download": "inBytesTotal", "upload": "outBytesTotal"}

    def __init__(self, coordinator, url, server_id, name, version):
        """Initialize the sensor."""
        super().__init__(coordinator)
        self._url = url
        self._server_id = server_id
        self._name = name
        self._version = version
        self._short_server_id = server_id.split("-")[0]
        self._last_total_value = self._current_value()
        self._last_updated = monotonic()
        self._state = 0

        self._attr_name = f"{self._short_server_id} {self._name}"
        self._attr_unique_id = f"{self._short_server_id}-{self._name}"
        self._attr_icon = "mdi:speedometer"
        self._attr_unit_of_measurement = DATA_RATE_MEGABYTES_PER_SECOND
        self._attr_device_info = {
            "identifiers": {(DOMAIN, self._server_id)},
            "name": f"Syncthing ({self._url})",
            "manufacturer": "Syncthing Team",
            "sw_version": self._version,
            "entry_type": "service",
        }

    @property
    def state(self):
        """Return the state of the sensor."""
        if not self.available:
            return
        return self._state

    @property
    def device_info(self):
        """Return device information."""
        return

    @property
    def extra_state_attributes(self):
        """Return the state attributes."""
        return {"total": self._current_value()}

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        current = self._current_value()
        now = monotonic()
        speed = (
            (current - self._last_total_value)
            / (now - self._last_updated)
            / 1024
            / 1024
        )
        self._state = round(speed, 2 if speed < 0.1 else 1)
        self._last_total_value = current
        self._last_updated = now
        super()._handle_coordinator_update()

    def _current_value(self):
        return self.coordinator.data["total"][self.NAMES[self._name]]
