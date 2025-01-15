"""Define coordinator functionality for HEOS the integration."""

from dataclasses import dataclass
from datetime import datetime, timedelta
import logging

from pyheos import (
    Credentials,
    Heos,
    HeosError,
    HeosNowPlayingMedia,
    HeosOptions,
    HeosPlayer,
    MediaItem,
    PlayerUpdateResult,
    const as heos_const,
)

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, CONF_PASSWORD, CONF_USERNAME, Platform
from homeassistant.core import HassJob, HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady, HomeAssistantError
from homeassistant.helpers import device_registry as dr, entity_registry as er
from homeassistant.helpers.event import async_call_later
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)
MIN_UPDATE_SOURCES = timedelta(seconds=1)


@dataclass
class HeosRuntimeData:
    """Runtime data and coordinators for HEOS config entries."""

    coordinator: "HeosCoordinator"


type HeosConfigEntry = ConfigEntry[HeosRuntimeData]


class HeosCoordinator(DataUpdateCoordinator[None]):
    """Define the HEOS integration coordinator.

    Control of HEOS devices is through the HEOS CLI Protocol and a connection is established to only one device
    in order to control all devices on the network. Data is pushed through events, which often contain the changed
    data. Other events represent larger changes (such as a group membership changing) and the coordinator will
    need to request new data.
    """

    def __init__(self, hass: HomeAssistant, config_entry: HeosConfigEntry) -> None:
        """Set up the coordinator."""
        self.host: str = config_entry.data[CONF_HOST]
        super().__init__(
            hass,
            _LOGGER,
            config_entry=config_entry,
            name=DOMAIN,
        )
        self.heos: Heos = self.__create_api()
        self._update_sources_pending: bool = False
        self._source_list: list[str] = []
        self._favorites: dict[int, MediaItem] = {}
        self._inputs: list[MediaItem] = []

    def __create_api(self) -> Heos:
        """Create the HEOS API instance based on the config entry."""
        credentials: Credentials | None = None
        assert self.config_entry is not None
        if self.config_entry.options:
            credentials = Credentials(
                self.config_entry.options[CONF_USERNAME],
                self.config_entry.options[CONF_PASSWORD],
            )

        # Setting all_progress_events=False ensures that we only receive a
        # media position update upon start of playback or when media changes
        return Heos(
            HeosOptions(
                self.host,
                all_progress_events=False,
                auto_reconnect=True,
                credentials=credentials,
            )
        )

    async def async_setup(self) -> None:
        """Connect to the HEOS device and add event callbacks."""
        # Add before connect as it may occur during connection
        self.heos.add_on_user_credentials_invalid(self.__auth_failure)

        # Connect to the device
        try:
            await self.heos.connect()
        except HeosError as error:
            _LOGGER.error("Unable to connect to host %s: %s", self.host, error)
            raise ConfigEntryNotReady from error

        # Load players
        try:
            await self.heos.get_players()
        except HeosError as error:
            _LOGGER.error("Unable to retrieve players: %s", error)
            raise ConfigEntryNotReady from error

        if not self.heos.is_signed_in:
            _LOGGER.warning(
                "The HEOS System is not logged in: Enter credentials in the integration options to access favorites and streaming services"
            )

        # Retrieve resources
        await self.__update_groups()
        await self.__update_sources()

        self.heos.add_on_disconnected(self.__disconnected)
        self.heos.add_on_connected(self.__reconnected)
        self.heos.add_on_controller_event(self.__controller_event)

    async def async_shutdown(self):
        """Disconnect all callbacks and disconnect from the device."""
        # Removes all callbacks connected through heos.add_on_* and player.add_on_*
        self.heos.dispatcher.disconnect_all()
        await self.heos.disconnect()
        return await super().async_shutdown()

    async def __auth_failure(self) -> None:
        """Handle callback when the user credentials are no longer valid.

        This may be raised during setup (inside Heos.connect()) or when calling commands in the API.
        """
        assert self.config_entry is not None
        self.config_entry.async_start_reauth(self.hass)

    async def __disconnected(self) -> None:
        """Handle when HEOS is disconnected.

        Notify entities to update, which will mark them as unavailable.
        """
        self.async_update_listeners()

    async def __reconnected(self) -> None:
        """Handle when HEOS reconnects.

        Update resources and notify entities to update so they become available.
        """
        await self.__update_players()
        # Update groups
        await self.__update_groups()
        # Build sources list
        await self.__update_sources()
        # Update entities
        self.async_update_listeners()

    async def __controller_event(self, event: str, data: PlayerUpdateResult | None):
        """Handle a controller event, such as players changing.

        Event values may be: EVENT_SOURCES_CHANGED, EVENT_PLAYERS_CHANGED,
        EVENT_GROUPS_CHANGED, or EVENT_USER_CHANGED

        EVENT_GROUPS_CHANGED is not explicitly handled since we only need to notify
        listeners to update and they will popualte the latest group member information.
        """
        if event == heos_const.EVENT_PLAYERS_CHANGED:
            assert data is not None
            if data.updated_player_ids:
                self.__update_player_ids(data.updated_player_ids)
        elif (
            event in (heos_const.EVENT_SOURCES_CHANGED, heos_const.EVENT_USER_CHANGED)
            and not self._update_sources_pending
        ):
            # Update the sources after a brief delay as we may have received multiple qualifying
            # events and HEOS often errors when immediately attempting to refresh.
            self._update_sources_pending = True

            async def update_sources_job(_: datetime | None = None):
                await self.__update_sources()
                self._update_sources_pending = False
                self.async_update_listeners()

            assert self.config_entry is not None
            self.config_entry.async_on_unload(
                async_call_later(
                    self.hass,
                    timedelta(seconds=1),
                    HassJob(
                        update_sources_job,
                        "heos_update_sources",
                        cancel_on_shutdown=True,
                    ),
                )
            )
        self.async_update_listeners()

    async def __update_players(self) -> None:
        """Update players."""
        try:
            player_updates = await self.heos.load_players()
        except HeosError as error:
            _LOGGER.error("Unable to refresh players: %s", error)
            return
        # After reconnecting, player_id may have changed
        if player_updates.updated_player_ids:
            self.__update_player_ids(player_updates.updated_player_ids)

    def __update_player_ids(self, mapped_ids: dict[int, int]):
        """Update the IDs in the device and entity registry."""
        device_registry = dr.async_get(self.hass)
        entity_registry = er.async_get(self.hass)
        # mapped_ids contains the mapped IDs (old:new)
        for old_id, new_id in mapped_ids.items():
            # update device registry
            entry = device_registry.async_get_device(
                identifiers={(DOMAIN, old_id)}  # type: ignore[arg-type]  # Fix in the future
            )
            new_identifiers = {(DOMAIN, new_id)}
            if entry:
                device_registry.async_update_device(
                    entry.id,
                    new_identifiers=new_identifiers,  # type: ignore[arg-type]  # Fix in the future
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

    async def __update_sources(self) -> None:
        """Rebuild the source list after a change event."""
        self._source_list.clear()
        # Get favorites only if reportedly signed in.
        if self.heos.is_signed_in:
            try:
                self._favorites = await self.heos.get_favorites()
            except HeosError as error:
                _LOGGER.error("Unable to retrieve favorites: %s", error)
            else:
                self._source_list.extend(
                    [favorite.name for favorite in self._favorites.values()]
                )
        # Get input sources (across all devices in the HEOS system)
        try:
            self._inputs = await self.heos.get_input_sources()
        except HeosError as error:
            _LOGGER.error("Unable to retrieve input sources: %s", error)
        else:
            self._source_list.extend([source.name for source in self._inputs])

    async def __update_groups(self) -> None:
        """Update the group information."""
        try:
            await self.heos.get_groups(refresh=True)
        except HeosError as error:
            _LOGGER.error("Unable to retrieve groups: %s", error)

    async def play_source(self, source: str, player: HeosPlayer) -> None:
        """Determine type of source and play it."""
        index = next(
            (
                index
                for index, favorite in self._favorites.items()
                if favorite.name == source
            ),
            None,
        )
        if index is not None:
            await player.play_preset_station(index)
            return

        input_source = next(
            (
                input_source
                for input_source in self._inputs
                if input_source.name == source
            ),
            None,
        )
        if input_source is not None:
            await player.play_input_source(input_source.media_id)
            return

        _LOGGER.error("Unknown source: %s", source)

    def get_favorite_index(self, name: str) -> int | None:
        """Get the index of a favorite by media_id,."""
        return next(
            (
                index
                for index, favorite in self._favorites.items()
                if favorite.name == name
            ),
            None,
        )

    def get_current_source(self, now_playing_media: HeosNowPlayingMedia) -> str | None:
        """Determine current source from now playing media."""
        # Match input by input_name:media_id
        if now_playing_media.source_id == heos_const.MUSIC_SOURCE_AUX_INPUT:
            return next(
                (
                    input_source.name
                    for input_source in self._inputs
                    if input_source.media_id == now_playing_media.media_id
                ),
                None,
            )
        # Try matching favorite by name:station or media_id:album_id
        return next(
            (
                source.name
                for source in self._favorites.values()
                if source.name == now_playing_media.station
                or source.media_id == now_playing_media.album_id
            ),
            None,
        )

    async def join_players(self, player_id: int, member_entity_ids: list[str]) -> None:
        """Join a player with a group of players."""
        member_ids: list[int] = []
        # Map entity IDs to player IDs
        entity_registry = er.async_get(self.hass)
        for entity_id in member_entity_ids:
            entity = entity_registry.async_get(entity_id)
            if entity is None:
                raise HomeAssistantError(f"Entity {entity_id} was not found.")
            if entity.platform != DOMAIN:
                raise HomeAssistantError(
                    f"Entity {entity_id} is not a HEOS media player entity."
                )
            member_ids.append(int(entity.unique_id))

        await self.heos.set_group(player_id, member_ids)

    async def unjoin_player(self, player_id: int) -> None:
        """Remove the player from any group."""
        # If the player is the group leader, this effectively removes the group.
        if group := next(
            (
                group
                for group in self.heos.groups.values()
                if group.lead_player_id == player_id
            ),
            None,
        ):
            await self.heos.set_group([player_id])
        # If the player is a group member, update the group to exclude it
        elif group := next(
            (
                group
                for group in self.heos.groups.values()
                if player_id in group.member_player_ids
            ),
            None,
        ):
            new_members = group.member_player_ids - [player_id]
            await self.heos.set_group([group.group_id, *new_members])
        else:
            _LOGGER.debug("Player %s is not in a group", player_id)

    def get_group_members(self, player_id: int) -> list[str] | None:
        """Get group member entity IDs for the current player."""
        group = next(
            (
                group
                for group in self.heos.groups.values()
                if group.lead_player_id == player_id
                or player_id in group.member_player_ids
            ),
            None,
        )
        if group is None:
            return None
        player_ids = [group.lead_player_id, *group.member_player_ids]
        entity_registry = er.async_get(self.hass)
        entity_ids: list[str] = []
        for member_id in player_ids:
            entity = entity_registry.async_get_entity_id(
                Platform.MEDIA_PLAYER,
                DOMAIN,
                str(member_id),
            )
            if entity is not None:
                entity_ids.append(entity)
        return entity_ids

    @property
    def source_list(self) -> list[str]:
        """Return the list of sources for all players."""
        return self._source_list
