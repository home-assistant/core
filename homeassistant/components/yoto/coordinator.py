"""Coordinator for the Yoto integration."""

from datetime import timedelta

import aiohttp
from yoto_api import AuthenticationError, Token, YotoManager, YotoPlayer

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_ACCESS_TOKEN
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.config_entry_oauth2_flow import OAuth2Session
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.util import dt as dt_util

from .const import _LOGGER, DOMAIN, LIBRARY_CLIENT_ID, SCAN_INTERVAL

# `/device-v2/devices/mine` returns the player list with id, name, online,
# deviceType. The matching `/device-v2/{id}/status` endpoint requires the
# `family:device-status:view` scope, which Yoto's developer dashboard does not
# expose to self-service apps yet, so we deliberately stop at the listing.
DEVICES_ENDPOINT = "https://api.yotoplay.com/device-v2/devices/mine"

type YotoConfigEntry = ConfigEntry[YotoDataUpdateCoordinator]


class YotoDataUpdateCoordinator(DataUpdateCoordinator[None]):
    """Coordinator that drives the Yoto cloud polling cycle."""

    config_entry: YotoConfigEntry

    def __init__(
        self,
        hass: HomeAssistant,
        entry: YotoConfigEntry,
        session: OAuth2Session,
    ) -> None:
        """Initialize the coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            config_entry=entry,
            name=DOMAIN,
            update_interval=SCAN_INTERVAL,
        )
        self.session = session
        self.yoto_manager = YotoManager(client_id=LIBRARY_CLIENT_ID)
        self._sync_token()

    def _sync_token(self) -> None:
        """Push the latest OAuth2 access token into the Yoto manager."""
        token = self.session.token
        expires_in = int(token.get("expires_in", 3600))
        self.yoto_manager.token = Token(
            access_token=token[CONF_ACCESS_TOKEN],
            refresh_token=token.get("refresh_token", ""),
            token_type=token.get("token_type", "Bearer"),
            valid_until=dt_util.utcnow() + timedelta(seconds=expires_in),
        )

    async def _async_update_data(self) -> None:
        """Fetch the latest player list from the cloud."""
        try:
            await self.session.async_ensure_token_valid()
        except aiohttp.ClientError as err:
            raise UpdateFailed(
                translation_domain=DOMAIN,
                translation_key="update_error",
                translation_placeholders={"error": str(err)},
            ) from err

        self._sync_token()

        try:
            await self._async_refresh_devices()
        except AuthenticationError as err:
            raise ConfigEntryAuthFailed(
                translation_domain=DOMAIN,
                translation_key="auth_error",
            ) from err
        except aiohttp.ClientError as err:
            raise UpdateFailed(
                translation_domain=DOMAIN,
                translation_key="update_error",
                translation_placeholders={"error": str(err)},
            ) from err

        if not self.yoto_manager.library:
            # The yoto-api Family parser raises on unexpected payloads
            # (e.g. when a member dict lacks `lastIp`). Log and continue
            # so the integration still surfaces basic player state without
            # the per-card metadata.
            try:
                await self.hass.async_add_executor_job(self.yoto_manager.update_library)
            except Exception as err:  # noqa: BLE001
                _LOGGER.warning("Could not load Yoto library metadata: %s", err)

        if self.yoto_manager.mqtt_client is None:
            await self.hass.async_add_executor_job(
                self.yoto_manager.connect_to_events, self._mqtt_event
            )

    async def _async_refresh_devices(self) -> None:
        """Fetch the player list and merge it into the manager state."""
        access_token = self.session.token[CONF_ACCESS_TOKEN]
        session = async_get_clientsession(self.hass)
        async with session.get(
            DEVICES_ENDPOINT,
            headers={"Authorization": f"Bearer {access_token}"},
        ) as response:
            if response.status in (401, 403):
                raise AuthenticationError(
                    f"Yoto rejected the access token ({response.status})"
                )
            response.raise_for_status()
            payload = await response.json()

        now = dt_util.utcnow()
        for item in payload.get("devices", []):
            player_id = item["deviceId"]
            player = self.yoto_manager.players.get(player_id)
            if player is None:
                player = YotoPlayer(id=player_id)
                self.yoto_manager.players[player_id] = player
            player.name = item.get("name")
            player.online = item.get("online")
            player.device_type = item.get("deviceType")
            player.last_updated_at = now

    def _mqtt_event(self) -> None:
        """Handle a real-time update pushed by the Yoto MQTT broker.

        Called from the paho-mqtt thread, so the listener notification has to
        be scheduled on the event loop.
        """
        self.hass.loop.call_soon_threadsafe(self.async_set_updated_data, None)

    async def async_shutdown(self) -> None:
        """Disconnect MQTT and cancel the update loop."""
        await super().async_shutdown()
        if self.yoto_manager.mqtt_client is not None:
            await self.hass.async_add_executor_job(self.yoto_manager.disconnect)
