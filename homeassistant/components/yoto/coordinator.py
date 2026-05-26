"""Coordinator for the Yoto integration."""

from datetime import datetime

import aiohttp
from yoto_api import Token, YotoClient, YotoError, YotoPlayer

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_ACCESS_TOKEN
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady, OAuth2TokenRequestError
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

    async def _async_setup(self) -> None:
        """Set up the coordinator."""
        try:
            await self.client.refresh()
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

        # The MQTT data/status topic is not pushed spontaneously; the firmware
        # only emits it in response to a command/status/request publish.
        self.config_entry.async_on_unload(
            async_track_time_interval(
                self.hass, self._async_status_push_tick, STATUS_PUSH_INTERVAL
            )
        )

    async def _async_update_data(self) -> dict[str, YotoPlayer]:
        """Fetch fresh data from the Yoto cloud."""
        # _async_setup already populated the client; skip the duplicate first fetch.
        if self.data is None:
            return self.client.players

        try:
            await self._session.async_ensure_token_valid()
        except (aiohttp.ClientError, OAuth2TokenRequestError) as err:
            raise UpdateFailed(
                translation_domain=DOMAIN,
                translation_key="update_error",
                translation_placeholders={"error": str(err)},
            ) from err

        self._sync_token()

        try:
            await self.client.refresh()
        except YotoError as err:
            raise UpdateFailed(
                translation_domain=DOMAIN,
                translation_key="update_error",
                translation_placeholders={"error": str(err)},
            ) from err

        return self.client.players

    async def _async_load_library(self) -> None:
        """Load the card library; failures only affect titles and artwork."""
        try:
            await self.client.update_library()
        except YotoError as err:
            _LOGGER.warning("Could not load Yoto card library: %s", err)

    async def _async_status_push_tick(self, _now: datetime) -> None:
        """Ask each player to push a fresh status snapshot over MQTT."""
        if not self.client.is_mqtt_connected:
            return
        # Fire-and-forget: the data/status response lands via the on_update
        # callback later, which already triggers async_set_updated_data.
        for device_id in list(self.client.players):
            await self.client.request_status_push(device_id)

    def _mqtt_event(self, _player: YotoPlayer) -> None:
        """Handle a real-time update pushed by the Yoto MQTT broker."""
        self.async_set_updated_data(self.client.players)

    async def async_shutdown(self) -> None:
        """Shut down the coordinator."""
        await self.client.disconnect_events()
        await super().async_shutdown()
