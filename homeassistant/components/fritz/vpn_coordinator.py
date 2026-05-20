"""WireGuard VPN coordinator for FRITZ!Box Tools (web UI API)."""

from datetime import timedelta
import logging
from typing import Any, cast

from fritzboxvpn import (
    API_KEY_ACTIVE,
    API_KEY_CONNECTED,
    API_KEY_NAME,
    FritzBoxVPNSession,
)
from fritzboxvpn.const import PROTOCOL_HTTP, PROTOCOL_HTTPS

from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import CONF_HOST, CONF_PASSWORD, CONF_SSL, CONF_USERNAME
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import (
    DEFAULT_SSL,
    DOMAIN,
    LOG_MSG_VPN_CONNECTIONS_REMOVED,
    SCAN_INTERVAL,
    VPN_AUTH_INDICATORS,
    VPN_RETRY_AFTER_SECONDS,
    VPN_STATUS_CONNECTED,
    VPN_STATUS_DISABLED,
    VPN_STATUS_ENABLED,
    VPN_STATUS_UNKNOWN,
)

_LOGGER = logging.getLogger(__name__)


def vpn_auth_failed(error: BaseException) -> bool:
    """Return True when the error indicates invalid VPN credentials."""
    message = str(error).lower()
    return any(indicator in message for indicator in VPN_AUTH_INDICATORS)


def vpn_web_ui_protocol(config: dict[str, Any]) -> str:
    """Return the WireGuard web UI protocol for the config entry."""
    return cast(
        str,
        PROTOCOL_HTTPS if config.get(CONF_SSL, DEFAULT_SSL) else PROTOCOL_HTTP,
    )


class FritzVpnCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    """Coordinator for WireGuard VPN connections on a FRITZ!Box."""

    def __init__(
        self,
        hass: HomeAssistant,
        config: dict[str, Any],
        *,
        entry_id: str,
    ) -> None:
        """Initialize the WireGuard VPN coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            name=f"{DOMAIN}_vpn",
            update_interval=timedelta(seconds=SCAN_INTERVAL),
        )
        self.entry_id = entry_id
        self._reauth_scheduled = False
        self.fritz_session = FritzBoxVPNSession(
            async_get_clientsession(hass),
            config[CONF_HOST],
            config[CONF_USERNAME],
            config[CONF_PASSWORD],
            protocol=vpn_web_ui_protocol(config),
        )

    def get_vpn_status(self, connection_uid: str) -> str:
        """Return the VPN status string for a connection."""
        if not self.data or connection_uid not in self.data:
            return VPN_STATUS_UNKNOWN
        conn = self.data[connection_uid]
        if not conn.get(API_KEY_ACTIVE, False):
            return VPN_STATUS_DISABLED
        if conn.get(API_KEY_CONNECTED, False):
            return VPN_STATUS_CONNECTED
        return VPN_STATUS_ENABLED

    def _schedule_reauth(self) -> None:
        if self._reauth_scheduled or not self.entry_id:
            return
        entry = self.hass.config_entries.async_get_entry(self.entry_id)
        if entry is None or entry.state != ConfigEntryState.LOADED:
            return
        self._reauth_scheduled = True
        entry.async_start_reauth(self.hass)

    def _update_failed(
        self, err: Exception, *, unexpected: bool = False
    ) -> UpdateFailed:
        if vpn_auth_failed(err):
            self._schedule_reauth()
        prefix = "Unexpected error" if unexpected else "Error"
        if unexpected:
            _LOGGER.exception("WireGuard VPN data update failed")
        message = f"{prefix} fetching WireGuard VPN data: {err}"
        if vpn_auth_failed(err):
            return UpdateFailed(message)
        return UpdateFailed(message, retry_after=VPN_RETRY_AFTER_SECONDS)

    def _log_removed_connections(
        self, previous_uids: set[str], connections: dict[str, Any]
    ) -> None:
        removed = previous_uids - connections.keys()
        if not removed:
            return
        names = [self.data.get(uid, {}).get(API_KEY_NAME, uid) for uid in removed]
        _LOGGER.warning(LOG_MSG_VPN_CONNECTIONS_REMOVED, names or list(removed))

    async def _async_update_data(self) -> dict[str, Any]:
        previous_uids = set(self.data) if self.data else set()
        try:
            connections = await self.fritz_session.async_get_vpn_connections()
        except (ConnectionError, ValueError, TimeoutError) as err:
            raise self._update_failed(err) from err
        except Exception as err:
            raise self._update_failed(err, unexpected=True) from err

        self._log_removed_connections(previous_uids, connections)
        self._reauth_scheduled = False
        return cast(dict[str, Any], connections)

    async def async_toggle_vpn(self, connection_uid: str, enable: bool) -> bool:
        """Toggle a WireGuard VPN connection on or off."""
        try:
            return cast(
                bool,
                await self.fritz_session.async_toggle_vpn(connection_uid, enable),
            )
        except Exception as err:
            if vpn_auth_failed(err):
                self._schedule_reauth()
            raise

    async def async_close(self) -> None:
        """Close the WireGuard VPN session."""
        await self.fritz_session.async_close()
