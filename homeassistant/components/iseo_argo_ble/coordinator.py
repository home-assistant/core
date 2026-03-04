"""IseoLogCoordinator — polls access logs from the ISEO lock."""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from typing import Any

from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives.asymmetric.ec import SECP224R1, derive_private_key

from homeassistant.components.bluetooth import async_ble_device_from_address
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import Context, HomeAssistant
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from iseo_argo_ble import (
    IseoAuthError,
    IseoClient,
    IseoConnectionError,
    LogEntry,
    UserEntry,
    UserSubType,
    battery_enum_to_pct,
)

from .const import (
    CONF_ADDRESS,
    CONF_ADMIN_PRIV_SCALAR,
    CONF_ADMIN_UUID,
    CONF_USER_MAP,
    DOMAIN,
    EVENT_TYPE,
)

_LOGGER = logging.getLogger(__name__)

_LOG_POLL_INTERVAL = timedelta(minutes=5)
_USER_REFRESH_INTERVAL = timedelta(hours=1)
# Event codes that mean the user list changed — trigger an immediate user-dir refresh.
_USER_CHANGE_EVENT_CODES = {15, 16, 17}  # WL_USER_ADDED, WL_USER_DELETED, WL_USER_UPDATED

# Event code → human-readable name (from ArgoLogStdConstants.java in the APK).
_EVENT_NAMES: dict[int, str] = {
    0: "Software upgrade",
    3: "Denied: phone not paired",
    4: "Denied: not registered",
    5: "Denied: wrong PIN",
    6: "Denied: battery too low",
    7: "Opened (delayed)",
    8: "Opened",
    9: "Passage mode on",
    10: "Passage mode off",
    11: "VIP mode on",
    12: "VIP mode off",
    13: "Denied: VIP mode active",
    14: "Whitelist cleared",
    15: "User added",
    16: "User deleted",
    17: "User updated",
    19: "Closed",
    20: "Closed (delayed)",
    21: "Whitelist full",
    28: "Master mode entered",
    29: "Master mode exited",
    31: "Denied: privacy mode",
    32: "Opened by emergency key",
    33: "Opened by handle",
    34: "Opened by key",
    39: "Privacy mode on",
    40: "Privacy mode off",
    45: "Opened by remote button",
    51: "Denied: validity not started",
    52: "Denied: validity expired",
    53: "Denied: time profile",
    57: "Open denied",
    62: "OEM auth error",
    68: "Denied: auth mismatch",
    75: "Opened (low battery)",
    76: "Closed (low battery)",
    78: "Master mode activated",
    79: "Master mode deactivated",
    80: "Open timeout",
    81: "Opened by latch",
    86: "Denied: no permission",
    88: "Denied: inhibited",
    89: "Denied: wrong password",
    93: "Admin access",
    102: "Mechanical key used",
    103: "Opened mechanically",
    104: "Door locked",
    105: "Door locked (out of frame)",
}


def event_name(code: int) -> str:
    """Return a human-readable label for an event code."""
    return _EVENT_NAMES.get(code, f"Event {code}")


def _bt_uuid_key(raw: str) -> str | None:
    """Return lower-case hex key if raw is a valid 32-char hex BT UUID, else None."""
    key = raw.lower()
    if len(key) == 32:
        try:
            bytes.fromhex(key)
            return key
        except ValueError:
            pass
    return None


def _resolve_actor(raw: str, user_dir: dict[str, str]) -> str:
    """Return a display name for raw user_info: looks up 32-char hex UUIDs in user_dir."""
    key = _bt_uuid_key(raw)
    if key is not None:
        return user_dir.get(key, raw)
    return raw


def entry_message(entry: LogEntry, user_dir: dict[str, str] | None = None) -> str:
    """Return a single-line description for a log entry."""
    raw = entry.user_info.strip() or entry.extra_description.strip()
    actor = _resolve_actor(raw, user_dir) if (raw and user_dir is not None) else raw
    name = event_name(entry.event_code)
    return f"{name} by {actor}" if actor else name


class IseoLogCoordinator(DataUpdateCoordinator[LogEntry | None]):
    """Periodically fetches the most recent access-log entries from the lock."""

    def __init__(
        self,
        hass: HomeAssistant,
        entry: ConfigEntry,
        uuid_bytes: bytes,
        identity_priv: Any,
        user_subtype: int = UserSubType.BT_SMARTPHONE,
    ) -> None:
        """Initialize the coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            name=f"ISEO Log {entry.data[CONF_ADDRESS]}",
            config_entry=entry,
            update_interval=_LOG_POLL_INTERVAL,
        )
        self._entry = entry
        self._uuid_bytes = uuid_bytes
        self._identity_priv = identity_priv
        self._user_subtype = user_subtype
        self._user_dir: dict[str, str] = {}
        self._user_dir_ts: datetime | None = None
        self._users: list[UserEntry] = []
        self._users_fetched: bool = False

        self.client = IseoClient(
            address=entry.data[CONF_ADDRESS],
            uuid_bytes=uuid_bytes,
            identity_priv=identity_priv,
            subtype=user_subtype,
            ble_device=async_ble_device_from_address(
                hass, entry.data[CONF_ADDRESS], connectable=True
            ),
        )

    @property
    def user_dir(self) -> dict[str, str]:
        """Return the current uuid_hex → name mapping."""
        return self._user_dir

    @property
    def users(self) -> list[UserEntry]:
        """Return the full whitelist user list from the last fetch."""
        return self._users

    @property
    def identity_priv(self) -> Any:
        """Return the gateway identity private key."""
        return self._identity_priv

    async def _refresh_user_dir(self) -> None:
        """Fetch the whitelist from the lock and rebuild the name directory."""
        try:
            admin_client = await self.hass.async_add_executor_job(
                self.make_admin_client
            )
            if admin_client is not None:
                fetch_client = admin_client
                skip = False
            else:
                self.client.update_ble_device(
                    async_ble_device_from_address(
                        self.hass,
                        self._entry.data[CONF_ADDRESS],
                        connectable=True,
                    )
                )
                fetch_client = self.client
                skip = True
            users: list[UserEntry] = await fetch_client.read_users(
                skip_login=skip
            )
        except (IseoConnectionError, IseoAuthError, Exception) as exc:
            _LOGGER.warning(
                "User directory refresh failed (actor names may be stale): %s",
                exc,
            )
            return

        self._users = users
        self._users_fetched = True
        self._user_dir = {
            u.uuid_hex.lower(): u.name or u.uuid_hex.upper() for u in users
        }
        self._user_dir_ts = datetime.now(tz=timezone.utc)
        _LOGGER.debug(
            "User directory refreshed: %d users (%d named)",
            len(users),
            sum(1 for u in users if u.name),
        )

    async def _async_update_data(self) -> LogEntry | None:
        """Fetch latest log entries from the lock."""
        try:
            self.client.update_ble_device(
                async_ble_device_from_address(
                    self.hass,
                    self._entry.data[CONF_ADDRESS],
                    connectable=True,
                )
            )
            entries = await self.client.gw_read_unread_logs(connect_timeout=20.0)
        except (IseoConnectionError, IseoAuthError) as exc:
            raise UpdateFailed(f"Log fetch failed: {exc}") from exc

        user_dir_refreshed = False
        if not self._users_fetched:
            await self._refresh_user_dir()
            user_dir_refreshed = True

        if not entries:
            return self.data

        now = datetime.now(tz=timezone.utc)
        if not user_dir_refreshed and (
            self._user_dir_ts is None
            or (now - self._user_dir_ts) >= _USER_REFRESH_INTERVAL
            or any(e.event_code in _USER_CHANGE_EVENT_CODES for e in entries)
        ):
            await self._refresh_user_dir()

        entity_id = self._get_lock_entity_id()
        user_map: dict[str, str] = self._entry.options.get(CONF_USER_MAP, {})
        for e in entries:
            raw_actor = e.user_info.strip() or e.extra_description.strip()
            actor = _resolve_actor(raw_actor, self._user_dir) if raw_actor else ""
            uuid_key = _bt_uuid_key(raw_actor) if raw_actor else None
            ha_user_id = user_map.get(uuid_key) if uuid_key else None
            event_ctx = Context(user_id=ha_user_id) if ha_user_id else None
            self.hass.bus.async_fire(
                EVENT_TYPE,
                {
                    "entity_id": entity_id,
                    "event_code": e.event_code,
                    "name": event_name(e.event_code),
                    "message": entry_message(e, self._user_dir),
                    "actor": actor,
                    "timestamp": e.timestamp.isoformat(),
                    "battery_pct": battery_enum_to_pct(e.battery),
                },
                context=event_ctx,
            )

        return entries[-1]

    def make_admin_client(self) -> IseoClient | None:
        """Return an IseoClient using the admin identity, or None if not configured.

        CPU-bound due to derive_private_key; callers must run in executor.
        """
        admin_uuid = self._entry.data.get(CONF_ADMIN_UUID)
        admin_scalar = self._entry.data.get(CONF_ADMIN_PRIV_SCALAR)
        if not admin_uuid or not admin_scalar:
            return None
        priv = derive_private_key(int(admin_scalar, 16), SECP224R1(), default_backend())
        return IseoClient(
            address=self._entry.data[CONF_ADDRESS],
            uuid_bytes=bytes.fromhex(admin_uuid),
            identity_priv=priv,
            subtype=UserSubType.BT_SMARTPHONE,
            ble_device=async_ble_device_from_address(
                self.hass,
                self._entry.data[CONF_ADDRESS],
                connectable=True,
            ),
        )

    def _get_lock_entity_id(self) -> str | None:
        """Look up the lock entity_id from the entity registry."""
        unique_id = (
            f"{self._entry.data[CONF_ADDRESS].replace(':', '').lower()}_lock"
        )
        registry = er.async_get(self.hass)
        return registry.async_get_entity_id("lock", DOMAIN, unique_id)
