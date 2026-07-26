"""Coordinator for the Yoto integration."""

from datetime import datetime
from typing import override

import aiohttp
from yoto_api import AuthenticationError, Token, YotoClient, YotoError, YotoPlayer

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_ACCESS_TOKEN
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import (
    ConfigEntryAuthFailed,
    ConfigEntryNotReady,
    OAuth2TokenRequestError,
    OAuth2TokenRequestReauthError,
)
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.config_entry_oauth2_flow import OAuth2Session
from homeassistant.helpers.event import async_track_time_interval
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.util import dt as dt_util

from .const import _LOGGER, DOMAIN, SCAN_INTERVAL, STATUS_PUSH_INTERVAL

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
        self._session = session
        self.client = YotoClient(session=async_get_clientsession(hass))
        self._subscribed_players: set[str] = set()
        self._sync_token()

    def _sync_token(self) -> None:
        """Sync the OAuth2 access token to the Yoto client."""
        token = self._session.token
        self.client.token = Token(
            access_token=token[CONF_ACCESS_TOKEN],
            refresh_token=token.get("refresh_token", ""),
            token_type=token.get("token_type", "Bearer"),
            valid_until=dt_util.utc_from_timestamp(token["expires_at"]),
        )

    @override
    async def _async_setup(self) -> None:
        """Set up the coordinator."""
        try:
            await self.client.refresh()
        except AuthenticationError as err:
            raise ConfigEntryAuthFailed(
                translation_domain=DOMAIN,
                translation_key="authentication_failed",
            ) from err
        except YotoError as err:
            raise ConfigEntryNotReady(
                translation_domain=DOMAIN,
                translation_key="update_error",
                translation_placeholders={"error": str(err)},
            ) from err

        await self._async_load_library()

        try:
            await self.client.connect_events(
                list(self.client.players), self._mqtt_event
            )
        except YotoError as err:
            raise ConfigEntryNotReady(
                translation_domain=DOMAIN,
                translation_key="update_error",
                translation_placeholders={"error": str(err)},
            ) from err

        self._subscribed_players = set(self.client.players)

        # The MQTT data/status topic is not pushed spontaneously; the firmware
        # only emits it in response to a command/status/request publish.
        self.config_entry.async_on_unload(
            async_track_time_interval(
                self.hass, self._async_status_push_tick, STATUS_PUSH_INTERVAL
            )
        )

    @override
    async def _async_update_data(self) -> dict[str, YotoPlayer]:
        """Fetch fresh data from the Yoto cloud."""
        try:
            await self._session.async_ensure_token_valid()
        except OAuth2TokenRequestReauthError as err:
            raise ConfigEntryAuthFailed(
                translation_domain=DOMAIN,
                translation_key="authentication_failed",
            ) from err
        except (aiohttp.ClientError, OAuth2TokenRequestError) as err:
            raise UpdateFailed(
                translation_domain=DOMAIN,
                translation_key="update_error",
                translation_placeholders={"error": str(err)},
            ) from err

        self._sync_token()

        try:
            await self.client.refresh()
        except AuthenticationError as err:
            raise ConfigEntryAuthFailed(
                translation_domain=DOMAIN,
                translation_key="authentication_failed",
            ) from err
        except YotoError as err:
            raise UpdateFailed(
                translation_domain=DOMAIN,
                translation_key="update_error",
                translation_placeholders={"error": str(err)},
            ) from err

        await self._async_sync_subscriptions()
        self._remove_stale_devices()
        return self.client.players

    async def _async_sync_subscriptions(self) -> None:
        """Subscribe new players to MQTT events and unsubscribe removed ones."""
        current = set(self.client.players)
        try:
            for device_id in current - self._subscribed_players:
                await self.client.subscribe_player_events(device_id)
            for device_id in self._subscribed_players - current:
                await self.client.unsubscribe_player_events(device_id)
        except YotoError as err:
            _LOGGER.warning("Could not update Yoto event subscriptions: %s", err)
            return
        self._subscribed_players = current

    def _remove_stale_devices(self) -> None:
        """Drop devices for players no longer returned by the account."""
        device_registry = dr.async_get(self.hass)
        for device in dr.async_entries_for_config_entry(
            device_registry, self.config_entry.entry_id
        ):
            player_id = next(
                (ident[1] for ident in device.identifiers if ident[0] == DOMAIN), None
            )
            if player_id is not None and player_id not in self.client.players:
                device_registry.async_remove_device(device.id)

    async def _async_load_library(self) -> None:
        """Load the card library and groups; failures only affect browsing."""
        try:
            await self.client.update_library()
        except YotoError as err:
            _LOGGER.warning("Could not load Yoto card library: %s", err)
        try:
            await self.client.update_groups()
        except YotoError as err:
            _LOGGER.warning("Could not load Yoto card groups: %s", err)

    async def _async_status_push_tick(self, _now: datetime) -> None:
        """Ask each player to push a fresh status snapshot over MQTT."""
        if not self.client.is_mqtt_connected:
            return
        for device_id in list(self.client.players):
            await self.client.request_player_status(device_id)

    def _mqtt_event(self, _player: YotoPlayer) -> None:
        """Handle a real-time update pushed by the Yoto MQTT broker."""
        self.async_set_updated_data(self.client.players)

    @override
    async def async_shutdown(self) -> None:
        """Shut down the coordinator."""
        await self.client.disconnect_events()
        await super().async_shutdown()
