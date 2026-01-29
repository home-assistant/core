"""Support for monitoring the Syncthing instance."""

from collections.abc import Mapping
from typing import Any

import aiosyncthing

from homeassistant.components.sensor import SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import PlatformNotReady
from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.event import async_track_time_interval

from . import SyncthingClient
from .const import (
    DEVICE_CONNECTED_RECEIVED,
    DEVICE_DISCONNECTED_RECEIVED,
    DEVICE_PAUSED_RECEIVED,
    DEVICE_RESUMED_RECEIVED,
    DOMAIN,
    FOLDER_PAUSED_RECEIVED,
    FOLDER_SUMMARY_RECEIVED,
    INITIAL_EVENTS_READY,
    SCAN_INTERVAL,
    SERVER_AVAILABLE,
    SERVER_UNAVAILABLE,
    STATE_CHANGED_RECEIVED,
)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
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
    async_add_entities(folder_entities)

    device_entities = [
        DeviceSensor(
            syncthing,
            server_id,
            device["deviceID"],
            device["name"],
            version["version"],
        )
        for device in config["devices"]
    ]

    async_add_entities(device_entities)


class FolderSensor(SensorEntity):
    """A Syncthing folder sensor."""

    _attr_should_poll = False
    _attr_translation_key = "syncthing_folder"

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
        "stateChanged": "state_changed",
    }

    def __init__(
        self,
        syncthing: SyncthingClient,
        server_id: str,
        folder_id: str,
        folder_label: str,
        version: str,
    ) -> None:
        """Initialize the sensor."""
        self._syncthing = syncthing
        self._server_id = server_id
        self._folder_id = folder_id
        self._folder_label = folder_label
        self._state = None
        self._unsub_timer = None

        self._short_server_id = server_id.split("-")[0]
        self._attr_name = f"{self._short_server_id} {folder_id} {folder_label}"
        self._attr_unique_id = f"{self._short_server_id}-{folder_id}"
        self._attr_device_info = DeviceInfo(
            entry_type=DeviceEntryType.SERVICE,
            identifiers={(DOMAIN, self._server_id)},
            manufacturer="Syncthing Team",
            name=f"Syncthing ({syncthing.url})",
            sw_version=version,
        )

    @property
    def native_value(self) -> str:
        """Return the state of the sensor."""
        return self._state["state"] if self._state else "unknown"

    @property
    def available(self) -> bool:
        """Could the device be accessed during the last update call."""
        return self._state is not None

    @property
    def extra_state_attributes(self) -> Mapping[str, Any] | None:
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

    async def async_added_to_hass(self) -> None:
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

    def _filter_state(self, state) -> dict:
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


class DeviceSensor(SensorEntity):
    """A Syncthing device sensor."""

    _attr_should_poll = False
    _attr_translation_key = "syncthing_device"

    STATE_ATTRIBUTES = {
        "deviceID": "device_id",
        "name": "name",
        "addresses": "addresses",
        "compression": "compression",
        "certName": "cert_name",
        "introducer": "introducer",
        "skipIntroductionRemovals": "skip_introduction_removals",
        "introducedBy": "introduced_by",
        "paused": "paused",
        "allowedNetworks": "allowed_networks",
        "autoAcceptFolders": "auto_accept_folders",
        "maxSendKbps": "max_send_kbps",
        "maxRecvKbps": "max_recv_kbps",
        "ignoredFolders": "ignored_folders",
        "maxRequestKiB": "max_request_kib",
        "untrusted": "untrusted",
        "remoteGUIPort": "remote_gui_port",
        "numConnections": "num_connections",
        "deviceName": "device_name",
        "clientName": "client_name",
        "clientVersion": "client_version",
        "addr": "addr",
        "state": "state",
    }

    def __init__(
        self,
        syncthing: SyncthingClient,
        server_id: str,
        device_id: str,
        device_label: str,
        version: str,
    ) -> None:
        """Initialize the sensor."""
        self._syncthing = syncthing
        self._server_id = server_id
        self._device_id = device_id
        self._device_label = device_label
        self._state = None
        self._unsub_timer = None

        self._short_server_id = server_id.split("-")[0]
        self._short_device_id = device_id.split("-")[0]
        self._attr_name = (
            f"{self._short_server_id} {self._short_device_id} {device_label}"
        )
        self._attr_unique_id = f"{self._short_server_id}-{device_id}"
        self._attr_device_info = DeviceInfo(
            entry_type=DeviceEntryType.SERVICE,
            identifiers={(DOMAIN, self._server_id)},
            manufacturer="Syncthing Team",
            name=f"Syncthing ({syncthing.url})",
            sw_version=version,
        )

    @property
    def native_value(self) -> str:
        """Return the state of the sensor."""
        return self._state["state"] if self._state else "unknown"

    @property
    def available(self) -> bool:
        """Could the device be accessed during the last update call."""
        return self._state is not None

    @property
    def extra_state_attributes(self) -> Mapping[str, Any] | None:
        """Return the state attributes."""
        return self._state

    async def async_update_status(self):
        """Request device status and update state."""
        try:
            state = await self._syncthing.config.devices(self._device_id)
        except aiosyncthing.exceptions.SyncthingError:
            self._state = None
        else:
            if state["deviceID"] == self._server_id:
                state["state"] = "online"
            else:
                state["state"] = (
                    self._state.get("state", "unknown") if self._state else "unknown"
                )

            self._state = self._update_state(state)

        self.async_write_ha_state()

    def subscribe(self):
        """Start polling syncthing device status."""
        if self._unsub_timer is None:

            async def refresh(event_time):
                """Get the latest data from Syncthing."""
                await self.async_update_status()

            self._unsub_timer = async_track_time_interval(
                self.hass, refresh, SCAN_INTERVAL
            )

    @callback
    def unsubscribe(self):
        """Stop polling syncthing device status."""
        if self._unsub_timer is not None:
            self._unsub_timer()
            self._unsub_timer = None

    async def async_added_to_hass(self) -> None:
        """Handle entity which will be added."""

        @callback
        def handle_device_connected(event):
            if self._state is not None:
                self._state = self._update_state(event["data"])
                self._state["state"] = "connected"
                self.async_write_ha_state()

        self.async_on_remove(
            async_dispatcher_connect(
                self.hass,
                f"{DEVICE_CONNECTED_RECEIVED}-{self._server_id}-{self._device_id}",
                handle_device_connected,
            )
        )

        @callback
        def handle_device_disconnected(event):
            if self._state is not None and self._state["state"] != "paused":
                self._state["state"] = "disconnected"
                self.async_write_ha_state()

        self.async_on_remove(
            async_dispatcher_connect(
                self.hass,
                f"{DEVICE_DISCONNECTED_RECEIVED}-{self._server_id}-{self._device_id}",
                handle_device_disconnected,
            )
        )

        @callback
        def handle_device_paused(event):
            if self._state is not None:
                self._state["state"] = "paused"
                self.async_write_ha_state()

        self.async_on_remove(
            async_dispatcher_connect(
                self.hass,
                f"{DEVICE_PAUSED_RECEIVED}-{self._server_id}-{self._device_id}",
                handle_device_paused,
            )
        )

        async def handle_device_resumed(event):
            if self._state is not None:
                self._state["state"] = "disconnected"
                self.async_write_ha_state()

        self.async_on_remove(
            async_dispatcher_connect(
                self.hass,
                f"{DEVICE_RESUMED_RECEIVED}-{self._server_id}-{self._device_id}",
                handle_device_resumed,
            )
        )

        @callback
        def handle_initial_events_ready():
            self._state = self._get_initial_device_state()
            self.async_write_ha_state()

        self.async_on_remove(
            async_dispatcher_connect(
                self.hass,
                f"{INITIAL_EVENTS_READY}-{self._server_id}",
                handle_initial_events_ready,
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

    def _get_initial_device_state(self) -> dict:
        """Get initial device state from stored events on startup."""
        # Default state
        state = "unknown" if self._server_id != self._device_id else "online"
        last_event: Mapping[str, Any] = {"data": {}}

        for event in [
            e
            for e in self._syncthing.get_initial_events()
            if e["data"].get("device") == self._device_id
            or e["data"].get("id") == self._device_id
        ]:
            if event["type"] == "DeviceConnected":
                last_event = event
                state = "connected"
            elif event["type"] == "DeviceDisconnected":
                last_event = event
                state = "disconnected" if state != "paused" else state
            elif event["type"] == "DevicePaused":
                state = "paused"
            elif event["type"] == "DeviceResumed":
                state = "disconnected"

        # Get additional attributes from last event with more info
        last_event["data"]["state"] = state
        return self._update_state(last_event["data"])

    def _update_state(self, updates) -> dict:
        # Select only needed state attributes and map their names
        state = self._state if self._state is not None else {}

        for key, value in updates.items():
            if key in self.STATE_ATTRIBUTES:
                state[key] = value

        return state
