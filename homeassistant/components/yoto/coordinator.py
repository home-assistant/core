"""Coordinator for the Yoto integration."""

import aiohttp
from yoto_api import AuthenticationError, Token, YotoError, YotoManager, YotoPlayer

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_ACCESS_TOKEN
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.config_entry_oauth2_flow import OAuth2Session
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.util import dt as dt_util

from .const import _LOGGER, DOMAIN, SCAN_INTERVAL

type YotoConfigEntry = ConfigEntry[YotoDataUpdateCoordinator]


class YotoDataUpdateCoordinator(DataUpdateCoordinator[dict[str, YotoPlayer]]):
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
        self.yoto_manager = YotoManager()
        self._sync_token()

    def _sync_token(self) -> None:
        """Push the latest OAuth2 access token into the Yoto manager."""
        token = self.session.token
        self.yoto_manager.token = Token(
            access_token=token[CONF_ACCESS_TOKEN],
            refresh_token=token.get("refresh_token", ""),
            token_type=token.get("token_type", "Bearer"),
            valid_until=dt_util.utc_from_timestamp(token["expires_at"]),
        )

    async def _async_setup(self) -> None:
        """Run one-shot setup: load the library and start the MQTT listener."""
        try:
            await self.hass.async_add_executor_job(self.yoto_manager.update_library)
        except YotoError as err:
            _LOGGER.warning("Could not load Yoto library metadata: %s", err)

        # Populate the player list before connecting so MQTT can subscribe
        # to each player's topic in the on_connect callback.
        try:
            await self.hass.async_add_executor_job(self.yoto_manager.update_player_list)
        except AuthenticationError as err:
            raise ConfigEntryAuthFailed(
                translation_domain=DOMAIN,
                translation_key="auth_error",
            ) from err

        await self.hass.async_add_executor_job(
            self.yoto_manager.connect_to_events, self._mqtt_event
        )

    async def _async_update_data(self) -> dict[str, YotoPlayer]:
        """Refresh the player list and self-heal the MQTT subscription."""
        # The first refresh runs right after _async_setup, which already
        # populated the manager. Skip the duplicate fetch.
        if self.data is None:
            return self.yoto_manager.players

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
            await self.hass.async_add_executor_job(self.yoto_manager.update_player_list)
        except AuthenticationError as err:
            raise ConfigEntryAuthFailed(
                translation_domain=DOMAIN,
                translation_key="auth_error",
            ) from err
        except YotoError as err:
            raise UpdateFailed(
                translation_domain=DOMAIN,
                translation_key="update_error",
                translation_placeholders={"error": str(err)},
            ) from err

        # Watchdog: paho-mqtt usually self-recovers, but if a connection
        # is permanently lost we'd never see it. Re-establish on demand.
        if not self._mqtt_connected():
            await self.hass.async_add_executor_job(self._reconnect_mqtt)

        return self.yoto_manager.players

    def _mqtt_connected(self) -> bool:
        """Return whether the MQTT client is currently connected."""
        client = self.yoto_manager.mqtt_client
        if client is None or client.client is None:
            return False
        return bool(client.client.is_connected())

    def _reconnect_mqtt(self) -> None:
        """Tear down the stale MQTT client and reopen the subscription."""
        if self.yoto_manager.mqtt_client is not None:
            self.yoto_manager.disconnect()
        self.yoto_manager.connect_to_events(self._mqtt_event)

    def _mqtt_event(self) -> None:
        """Handle a real-time update pushed by the Yoto MQTT broker."""
        # Called from the paho-mqtt thread.
        self.hass.loop.call_soon_threadsafe(
            self.async_set_updated_data, self.yoto_manager.players
        )

    async def async_shutdown(self) -> None:
        """Disconnect MQTT, then cancel the update loop."""
        if self.yoto_manager.mqtt_client is not None:
            await self.hass.async_add_executor_job(self.yoto_manager.disconnect)
        await super().async_shutdown()
