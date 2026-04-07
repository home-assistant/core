"""Data update coordinator for the Jellyfin integration."""

from __future__ import annotations

from datetime import timedelta
from typing import Any

from jellyfin_apiclient_python import JellyfinClient

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.storage import Store
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from .const import CONF_CLIENT_DEVICE_ID, DOMAIN, LOGGER, USER_APP_NAME

type JellyfinConfigEntry = ConfigEntry[JellyfinDataUpdateCoordinator]

_STORAGE_VERSION = 1


def _device_info_from_session(session: dict[str, Any]) -> dict[str, Any]:
    """Extract stable device info from a session for persistent storage."""
    return {
        "DeviceId": session["DeviceId"],
        "DeviceName": session["DeviceName"],
        "Client": session["Client"],
        "ApplicationVersion": session["ApplicationVersion"],
        "Capabilities": session.get("Capabilities", {}),
        "SupportsRemoteControl": session.get("SupportsRemoteControl", False),
    }


class JellyfinDataUpdateCoordinator(DataUpdateCoordinator[dict[str, dict[str, Any]]]):
    """Data update coordinator for the Jellyfin integration."""

    config_entry: JellyfinConfigEntry

    def __init__(
        self,
        hass: HomeAssistant,
        config_entry: JellyfinConfigEntry,
        api_client: JellyfinClient,
        system_info: dict[str, Any],
        user_id: str,
    ) -> None:
        """Initialize the coordinator."""
        super().__init__(
            hass=hass,
            logger=LOGGER,
            config_entry=config_entry,
            name=DOMAIN,
            update_interval=timedelta(seconds=10),
        )
        self.api_client = api_client
        self.server_id: str = system_info["Id"]
        self.server_name: str = system_info["Name"]
        self.server_version: str | None = system_info.get("Version")
        self.client_device_id: str = config_entry.data[CONF_CLIENT_DEVICE_ID]
        self.user_id: str = user_id

        # Persistent devices: seen at least once with SupportsPersistentIdentifier=True.
        # Persisted to storage and used to recreate entities after HA restarts.
        self.known_devices: dict[str, dict[str, Any]] = {}

        # Ephemeral devices: active session with SupportsPersistentIdentifier=False
        # (e.g. web browsers). In-memory only; reset each poll. Entities are created
        # while the session is active and removed when it ends.
        self.ephemeral_devices: dict[str, dict[str, Any]] = {}

        # Persisted map of session_id -> device_id for unique_id migration.
        # Allows migrating offline devices that had session-based unique_ids.
        self.session_device_map: dict[str, str] = {}

        # Tracks which device_ids already have HA entities created.
        self.device_player_ids: set[str] = set()
        self.device_remote_ids: set[str] = set()

        # Legacy sets kept for compatibility — no longer used internally.
        self.session_ids: set[str] = set()
        self.remote_session_ids: set[str] = set()
        self.device_ids: set[str] = set()

        self._store: Store[dict[str, Any]] = Store(
            hass,
            _STORAGE_VERSION,
            f"jellyfin_{config_entry.entry_id}_devices",
        )
        self._store_loaded = False
        self._store_needs_migration = False

    async def _async_update_data(self) -> dict[str, dict[str, Any]]:
        """Get the latest data from Jellyfin.

        Returns active sessions keyed by device_id (not session_id).
        Known but offline devices are tracked in self.known_devices but
        not included in the returned dict.
        """
        if not self._store_loaded:
            stored = await self._store.async_load()
            if stored:
                if "known_devices" in stored:
                    # Current format
                    self.known_devices = stored["known_devices"]
                    self.session_device_map = stored.get("session_device_map", {})
                else:
                    # Legacy format: bare dict of known_devices (no session map).
                    # Mark dirty so it gets rewritten in the new format.
                    self.known_devices = stored
                    self._store_needs_migration = True
            self._store_loaded = True

        sessions = await self.hass.async_add_executor_job(
            self.api_client.jellyfin.sessions
        )

        if sessions is None:
            return {}

        active: dict[str, dict[str, Any]] = {}
        self.ephemeral_devices = {}
        _store_dirty = self._store_needs_migration
        self._store_needs_migration = False
        for session in sessions:
            if (
                session["DeviceId"] == self.client_device_id
                or session["Client"] == USER_APP_NAME
            ):
                continue
            device_id = session["DeviceId"]
            active[device_id] = session
            if session.get("Capabilities", {}).get(
                "SupportsPersistentIdentifier", False
            ):
                new_device_info = _device_info_from_session(session)
                if self.known_devices.get(device_id) != new_device_info:
                    self.known_devices[device_id] = new_device_info
                    _store_dirty = True
                new_session_map = session["Id"]
                if self.session_device_map.get(new_session_map) != device_id:
                    self.session_device_map[new_session_map] = device_id
                    _store_dirty = True
            else:
                self.ephemeral_devices[device_id] = _device_info_from_session(session)

        self.device_ids = set(active.keys())

        if _store_dirty:
            await self._store.async_save(
                {
                    "known_devices": self.known_devices,
                    "session_device_map": self.session_device_map,
                }
            )

        return active

    async def async_persist(self) -> None:
        """Persist known_devices and session_device_map to storage."""
        await self._store.async_save(
            {
                "known_devices": self.known_devices,
                "session_device_map": self.session_device_map,
            }
        )
