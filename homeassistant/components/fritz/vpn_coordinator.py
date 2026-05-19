"""WireGuard VPN coordinator for FRITZ!Box Tools (web UI API)."""

from __future__ import annotations

import inspect
import logging
from datetime import timedelta
from typing import Any

from fritzboxvpn import (
    API_KEY_ACTIVE,
    API_KEY_CONNECTED,
    API_KEY_NAME,
    FritzBoxVPNSession,
)

from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import CONF_HOST, CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import (
    DOMAIN,
    SCAN_INTERVAL,
    VPN_AUTH_INDICATORS,
    VPN_RETRY_AFTER_SECONDS,
    VPN_STATUS_CONNECTED,
    VPN_STATUS_DISABLED,
    VPN_STATUS_ENABLED,
    VPN_STATUS_UNKNOWN,
)

_LOGGER = logging.getLogger(__name__)


class FritzVpnCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    """Coordinator for WireGuard VPN connections on a FRITZ!Box."""

    def __init__(
        self,
        hass: HomeAssistant,
        config: dict[str, Any],
        *,
        entry_id: str,
    ) -> None:
        """Initialize the VPN coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            name=f"{DOMAIN}_vpn",
            update_interval=timedelta(seconds=SCAN_INTERVAL),
        )
        self.config = config
        self.entry_id = entry_id
        self._reauth_scheduled = False
        self.fritz_session = FritzBoxVPNSession(
            async_get_clientsession(hass),
            config[CONF_HOST],
            config[CONF_USERNAME],
            config[CONF_PASSWORD],
        )

    def get_vpn_status(self, connection_uid: str) -> str:
        """Return textual VPN status for a connection."""
        if not self.data or connection_uid not in self.data:
            return VPN_STATUS_UNKNOWN
        conn = self.data[connection_uid]
        if not conn.get(API_KEY_ACTIVE, False):
            return VPN_STATUS_DISABLED
        if conn.get(API_KEY_CONNECTED, False):
            return VPN_STATUS_CONNECTED
        return VPN_STATUS_ENABLED

    def _is_auth_error(self, error: Exception) -> bool:
        """Return True when the error indicates invalid credentials."""
        message = str(error).lower()
        return any(indicator in message for indicator in VPN_AUTH_INDICATORS)

    def _schedule_reauth(self) -> None:
        """Start re-authentication once per auth failure cycle."""
        if self._reauth_scheduled:
            return
        entry = self.hass.config_entries.async_get_entry(self.entry_id)
        if entry is None or entry.state != ConfigEntryState.LOADED:
            return
        self._reauth_scheduled = True
        _LOGGER.warning(
            "WireGuard VPN authentication failed; starting reauth for entry %s",
            self.entry_id,
        )
        self.hass.async_create_task(self._async_start_reauth(entry))

    async def _async_start_reauth(self, entry: Any) -> None:
        """Start re-authentication for the config entry."""
        result = entry.async_start_reauth(self.hass)
        if inspect.isawaitable(result):
            await result

    async def _async_update_data(self) -> dict[str, Any]:
        """Fetch WireGuard VPN connection state from the FRITZ!Box."""
        try:
            connections = await self.fritz_session.async_get_vpn_connections()
        except (ConnectionError, ValueError, TimeoutError) as err:
            if self._is_auth_error(err):
                self._schedule_reauth()
                raise UpdateFailed(f"Error fetching WireGuard VPN data: {err}") from err
            raise UpdateFailed(
                f"Error fetching WireGuard VPN data: {err}",
                retry_after=VPN_RETRY_AFTER_SECONDS,
            ) from err
        except Exception as err:
            if self._is_auth_error(err):
                self._schedule_reauth()
                raise UpdateFailed(
                    f"Unexpected error fetching WireGuard VPN data: {err}"
                ) from err
            _LOGGER.exception("Unexpected error fetching WireGuard VPN data")
            raise UpdateFailed(
                f"Unexpected error fetching WireGuard VPN data: {err}",
                retry_after=VPN_RETRY_AFTER_SECONDS,
            ) from err
        else:
            self._reauth_scheduled = False
            return connections

    async def async_toggle_vpn(self, connection_uid: str, enable: bool) -> bool:
        """Enable or disable a WireGuard VPN connection."""
        try:
            return await self.fritz_session.async_toggle_vpn(connection_uid, enable)
        except Exception as err:
            if self._is_auth_error(err):
                self._schedule_reauth()
            raise

    async def async_close(self) -> None:
        """Close the HTTP session."""
        await self.fritz_session.async_close()
