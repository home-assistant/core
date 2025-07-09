"""HEOS integration coordinator.

Control of all HEOS devices is through connection to a single device. Data is pushed through events.
The coordinator is responsible for refreshing data in response to system-wide events and notifying
entities to update. Entities subscribe to entity-specific updates within the entity class itself.
"""

from collections.abc import Callable, Sequence
import logging
from typing import Any

from pyheos import (
    Credentials,
    Heos,
    HeosError,
    HeosNowPlayingMedia,
    HeosOptions,
    HeosPlayer,
    MediaItem,
    MediaType,
    PlayerUpdateResult,
    const,
)

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, CONF_PASSWORD, CONF_USERNAME, Platform
from homeassistant.core import CALLBACK_TYPE, HomeAssistant, callback
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers import device_registry as dr, entity_registry as er
from homeassistant.helpers.debounce import Debouncer
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

type HeosConfigEntry = ConfigEntry[HeosCoordinator]


class HeosCoordinator(DataUpdateCoordinator[None]):
    """Define the HEOS integration coordinator."""

    def __init__(self, hass: HomeAssistant, config_entry: HeosConfigEntry) -> None:
        """Set up the coordinator and set in config_entry."""
        credentials: Credentials | None = None
        if config_entry.options:
            credentials = Credentials(
                config_entry.options[CONF_USERNAME], config_entry.options[CONF_PASSWORD]
            )
        # Setting all_progress_events=False ensures that we only receive a
        # media position update upon start of playback or when media changes
        self.heos = Heos(
            HeosOptions(
                config_entry.data[CONF_HOST],
                all_progress_events=False,
                auto_reconnect=True,
                auto_failover=True,
                credentials=credentials,
            )
        )
        self._platform_callbacks: list[Callable[[Sequence[HeosPlayer]], None]] = []
        self._update_sources_debouncer = Debouncer(
            hass,
            _LOGGER,
            immediate=True,
            cooldown=2.0,
            function=self._async_update_sources,
        )
        self._source_list: list[str] = []
        self._favorites: dict[int, MediaItem] = {}
        self._inputs: Sequence[MediaItem] = []
        super().__init__(hass, _LOGGER, config_entry=config_entry, name=DOMAIN)

    @property
    def host(self) -> str:
        """Get the host address of the device."""
        return self.heos.current_host

    @property
    def inputs(self) -> Sequence[MediaItem]:
        """Get input sources across all devices."""
        return self._inputs

    @property
    def favorites(self) -> dict[int, MediaItem]:
        """Get favorite stations."""
        return self._favorites

    async def async_setup(self) -> None:
        """Set up the coordinator; connect to the host; and retrieve initial data."""
        # Add before connect as it may occur during initial connection
        self.heos.add_on_user_credentials_invalid(self._async_on_auth_failure)
        # Connect to the device
        try:
            await self.heos.connect()
        except HeosError as error:
            _LOGGER.debug("Unable to connect to %s", self.host, exc_info=True)
            raise ConfigEntryNotReady(
                translation_domain=DOMAIN,
                translation_key="unable_to_connect",
                translation_placeholders={"host": self.host},
            ) from error
        # Load players
        try:
            await self.heos.get_players()
        except HeosError as error:
            _LOGGER.debug("Unexpected error retrieving players", exc_info=True)
            raise ConfigEntryNotReady(
                translation_domain=DOMAIN, translation_key="unable_to_get_players"
            ) from error

        if not self.heos.is_signed_in:
            _LOGGER.warning(
                "The HEOS System is not logged in: Enter credentials in the integration options to access favorites and streaming services"
            )
        # Retrieve initial data
        await self._async_update_groups()
        await self._async_update_sources()
        # Attach event callbacks
        self.heos.add_on_disconnected(self._async_on_disconnected)
        self.heos.add_on_connected(self._async_on_reconnected)
        self.heos.add_on_controller_event(self._async_on_controller_event)

    async def async_shutdown(self) -> None:
        """Disconnect all callbacks and disconnect from the device."""
        self.heos.dispatcher.disconnect_all()  # Removes all connected through heos.add_on_* and player.add_on_*
        await self.heos.disconnect()
        await super().async_shutdown()

    def async_add_listener(
        self, update_callback: CALLBACK_TYPE, context: Any = None
    ) -> Callable[[], None]:
        """Add a listener for the coordinator."""
        remove_listener = super().async_add_listener(update_callback, context)
        # Update entities so group_member entity_ids fully populate.
        self.async_update_listeners()
        return remove_listener

    def async_add_platform_callback(
        self, add_entities_callback: Callable[[Sequence[HeosPlayer]], None]
    ) -> None:
        """Add a callback to add entities for a platform."""
        self._platform_callbacks.append(add_entities_callback)

    def _async_handle_player_update_result(
        self, update_result: PlayerUpdateResult
    ) -> None:
        """Handle a player update result."""
        if update_result.added_player_ids and self._platform_callbacks:
            new_players = [
                self.heos.players[player_id]
                for player_id in update_result.added_player_ids
            ]
            for add_entities_callback in self._platform_callbacks:
                add_entities_callback(new_players)

        if update_result.updated_player_ids:
            self._async_update_player_ids(update_result.updated_player_ids)

    async def _async_on_auth_failure(self) -> None:
        """Handle when the user credentials are no longer valid."""
        assert self.config_entry is not None
        self.config_entry.async_start_reauth(self.hass)

    async def _async_on_disconnected(self) -> None:
        """Handle when disconnected so entities are marked unavailable."""
        _LOGGER.warning("Connection to HEOS host %s lost", self.host)
        self.async_update_listeners()

    async def _async_on_reconnected(self) -> None:
        """Handle when reconnected so resources are updated and entities marked available."""
        assert self.config_entry is not None
        if self.host != self.config_entry.data[CONF_HOST]:
            self.hass.config_entries.async_update_entry(
                self.config_entry, data={CONF_HOST: self.host}
            )
            _LOGGER.warning("Successfully failed over to HEOS host %s", self.host)
        else:
            _LOGGER.warning("Successfully reconnected to HEOS host %s", self.host)
        await self._async_update_sources()
        self.async_update_listeners()

    async def _async_on_controller_event(
        self, event: str, data: PlayerUpdateResult | None = None
    ) -> None:
        """Handle a controller event, such as players or groups changed."""
        if event == const.EVENT_PLAYERS_CHANGED:
            assert data is not None
            self._async_handle_player_update_result(data)
        elif event in (const.EVENT_SOURCES_CHANGED, const.EVENT_USER_CHANGED):
            # Debounce because we may have received multiple qualifying events in rapid succession.
            await self._update_sources_debouncer.async_call()
        self.async_update_listeners()

    def _async_update_player_ids(self, updated_player_ids: dict[int, int]) -> None:
        """Update the IDs in the device and entity registry."""
        device_registry = dr.async_get(self.hass)
        entity_registry = er.async_get(self.hass)
        # updated_player_ids contains the mapped IDs in format old:new
        for old_id, new_id in updated_player_ids.items():
            # update device registry
            entry = device_registry.async_get_device(
                identifiers={(DOMAIN, str(old_id))}
            )
            if entry:
                new_identifiers = entry.identifiers.copy()
                new_identifiers.remove((DOMAIN, str(old_id)))
                new_identifiers.add((DOMAIN, str(new_id)))
                device_registry.async_update_device(
                    entry.id,
                    new_identifiers=new_identifiers,
                )
                _LOGGER.debug(
                    "Updated device %s identifiers to %s", entry.id, new_identifiers
                )
            # update entity registry
            entity_id = entity_registry.async_get_entity_id(
                Platform.MEDIA_PLAYER, DOMAIN, str(old_id)
            )
            if entity_id:
                entity_registry.async_update_entity(
                    entity_id, new_unique_id=str(new_id)
                )
                _LOGGER.debug("Updated entity %s unique id to %s", entity_id, new_id)

    async def _async_update_groups(self) -> None:
        """Update group information."""
        try:
            await self.heos.get_groups(refresh=True)
        except HeosError as error:
            _LOGGER.error("Unable to retrieve groups: %s", error)

    async def _async_update_sources(self) -> None:
        """Build source list for entities."""
        self._source_list.clear()
        # Get favorites only if reportedly signed in.
        if self.heos.is_signed_in:
            try:
                self._favorites = await self.heos.get_favorites()
            except HeosError as error:
                _LOGGER.error("Unable to retrieve favorites: %s", error)
            else:
                self._source_list.extend(
                    favorite.name for favorite in self._favorites.values()
                )
        # Get input sources (across all devices in the HEOS system)
        try:
            self._inputs = await self.heos.get_input_sources()
        except HeosError as error:
            _LOGGER.error("Unable to retrieve input sources: %s", error)
        else:
            self._source_list.extend([source.name for source in self._inputs])

    @callback
    def async_get_source_list(self) -> list[str]:
        """Return the list of sources for players."""
        return list(self._source_list)

    @callback
    def async_get_favorite_index(self, name: str) -> int | None:
        """Get the index of a favorite by name."""
        for index, favorite in self._favorites.items():
            if favorite.name == name:
                return index
        return None

    @callback
    def async_get_current_source(
        self, now_playing_media: HeosNowPlayingMedia
    ) -> str | None:
        """Determine current source from now playing media (either input source or favorite)."""
        # Try matching input source
        if now_playing_media.source_id == const.MUSIC_SOURCE_AUX_INPUT:
            # If playing a remote input, name will match station
            for input_source in self._inputs:
                if input_source.name == now_playing_media.station:
                    return input_source.name
            # If playing a local input, match media_id. This needs to be a second loop as media_id
            # will match both local and remote inputs, so prioritize remote match by name first.
            for input_source in self._inputs:
                if input_source.media_id == now_playing_media.media_id:
                    return input_source.name
        # Try matching favorite
        if now_playing_media.type == MediaType.STATION:
            # Some stations match on name:station, others match on media_id:album_id
            for favorite in self._favorites.values():
                if (
                    favorite.name == now_playing_media.station
                    or favorite.media_id == now_playing_media.album_id
                ):
                    return favorite.name
        return None
