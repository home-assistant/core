"""DataUpdateCoordinator for FritzBox VPN integration."""

import logging
from collections.abc import Callable
from datetime import timedelta
from typing import Any

from fritzboxvpn import (
    API_KEY_ACTIVE,
    API_KEY_CONNECTED,
    API_KEY_NAME,
    FritzBoxVPNSession,
)
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import (
    AUTH_INDICATORS,
    CONF_UPDATE_INTERVAL,
    DEFAULT_UPDATE_INTERVAL,
    DOMAIN,
    LOG_MSG_VPN_CONNECTIONS_REMOVED,
    LOG_MSG_VPN_CONNECTIONS_REMOVED_HINT,
    NAME_FRITZBOX,
    RETRY_AFTER_SECONDS,
    STATUS_CONNECTED,
    STATUS_DISABLED,
    STATUS_ENABLED,
    STATUS_UNKNOWN,
    UPDATE_INTERVAL_MAX,
    UPDATE_INTERVAL_MIN,
    host_from_config,
)

_LOGGER = logging.getLogger(__name__)


def normalize_update_interval(value: Any) -> int:
    """Update interval as int in valid range. SSOT for parsing."""
    def clamp(n: int) -> int:
        if UPDATE_INTERVAL_MIN <= n <= UPDATE_INTERVAL_MAX:
            return n
        _LOGGER.warning(
            "update_interval %d out of range (%d–%d), using default %s",
            n, UPDATE_INTERVAL_MIN, UPDATE_INTERVAL_MAX, DEFAULT_UPDATE_INTERVAL,
        )
        return DEFAULT_UPDATE_INTERVAL

    if value is None:
        return DEFAULT_UPDATE_INTERVAL
    if isinstance(value, int):
        return clamp(value)
    try:
        return clamp(int(value))
    except (ValueError, TypeError):
        _LOGGER.warning(
            "Invalid update_interval value %r, using default %s",
            value,
            DEFAULT_UPDATE_INTERVAL,
        )
        return DEFAULT_UPDATE_INTERVAL


def _resolve_update_interval_seconds(
    config: dict[str, Any],
    options: dict[str, Any] | None,
) -> int:
    """Resolve update interval from options, then config, then default."""
    options_dict = options or {}
    value = (
        options_dict.get(CONF_UPDATE_INTERVAL)
        or config.get(CONF_UPDATE_INTERVAL)
        or DEFAULT_UPDATE_INTERVAL
    )
    return normalize_update_interval(value)


class FritzBoxVPNCoordinator(DataUpdateCoordinator):
    """Coordinator for FritzBox VPN data."""

    def __init__(
        self,
        hass: HomeAssistant,
        config: dict[str, Any],
        options: dict[str, Any] | None = None,
        entry_id: str | None = None,
        on_orphaned_removed: Callable[[str, set[str]], None] | None = None,
    ):
        update_interval_seconds = _resolve_update_interval_seconds(config, options)

        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=timedelta(seconds=update_interval_seconds),
        )
        self.fritz_session = FritzBoxVPNSession(
            async_get_clientsession(hass),
            host_from_config(config),
            config[CONF_USERNAME],
            config[CONF_PASSWORD],
        )
        self.config = config
        self.entry_id = entry_id
        self._reauth_scheduled = False
        self._on_orphaned_removed = on_orphaned_removed

    def get_vpn_status(self, connection_uid: str) -> str:
        """Get the textual status of a VPN connection."""
        if not self.data or connection_uid not in self.data:
            return STATUS_UNKNOWN
        conn = self.data[connection_uid]
        active = conn.get(API_KEY_ACTIVE, False)
        connected = conn.get(API_KEY_CONNECTED, False)
        if not active:
            return STATUS_DISABLED
        return STATUS_CONNECTED if connected else STATUS_ENABLED

    def _is_auth_error(self, error: Exception) -> bool:
        """True if error message indicates authentication failure."""
        return any(ind in str(error).lower() for ind in AUTH_INDICATORS)

    def _schedule_reauth(self) -> None:
        """Start re-authentication flow once per auth failure cycle."""
        if self._reauth_scheduled or not self.entry_id:
            return
        entry = self.hass.config_entries.async_get_entry(self.entry_id)
        if entry is None or entry.state != ConfigEntryState.LOADED:
            return
        self._reauth_scheduled = True
        _LOGGER.warning(
            "Authentication failed; starting reauth flow for entry %s", self.entry_id
        )
        self.hass.async_create_task(entry.async_start_reauth(self.hass))

    async def _async_update_data(self) -> dict[str, Any]:
        """Fetch latest VPN data from Fritz!Box."""
        previous_uids = set(self.data.keys()) if self.data else set()
        try:
            connections = await self.fritz_session.async_get_vpn_connections()
            if previous_uids:
                current_uids = set(connections.keys())
                removed_uids = previous_uids - current_uids
                if removed_uids:
                    names = [
                        self.data.get(uid, {}).get(API_KEY_NAME, uid)
                        for uid in removed_uids
                    ]
                    _LOGGER.warning(
                        LOG_MSG_VPN_CONNECTIONS_REMOVED,
                        NAME_FRITZBOX,
                        names or list(removed_uids),
                    )
                    _LOGGER.info(LOG_MSG_VPN_CONNECTIONS_REMOVED_HINT)
                    if self._on_orphaned_removed and self.entry_id:
                        self._on_orphaned_removed(self.entry_id, current_uids)
            self._reauth_scheduled = False
            return connections
        except (ConnectionError, ValueError) as err:
            if self._is_auth_error(err):
                self._schedule_reauth()
                raise UpdateFailed(f"Error fetching VPN data: {err}") from err
            raise UpdateFailed(
                f"Error fetching VPN data: {err}",
                retry_after=RETRY_AFTER_SECONDS,
            ) from err
        except TimeoutError as err:
            raise UpdateFailed(
                f"Error fetching VPN data: {err}",
                retry_after=RETRY_AFTER_SECONDS,
            ) from err
        except Exception as err:
            if self._is_auth_error(err):
                self._schedule_reauth()
                raise UpdateFailed(f"Unexpected error fetching VPN data: {err}") from err
            _LOGGER.exception("Unexpected error fetching VPN data")
            raise UpdateFailed(
                f"Unexpected error fetching VPN data: {err}",
                retry_after=RETRY_AFTER_SECONDS,
            ) from err

    async def toggle_vpn(self, connection_uid: str, enable: bool) -> bool:
        """Toggle VPN on/off; schedule reauth on authentication errors."""
        try:
            return await self.fritz_session.async_toggle_vpn(connection_uid, enable)
        except Exception as err:
            if self._is_auth_error(err):
                self._schedule_reauth()
            raise
