"""Support for interfacing with the HASS MPRIS agent."""

from __future__ import annotations

import asyncio
from collections.abc import AsyncGenerator
import json
import re
from typing import Any, NotRequired, TypedDict, cast

from hassmpris.proto import mpris_pb2
import hassmpris_client

from homeassistant.components.media_player import (
    MediaPlayerDeviceClass,
    MediaPlayerEntity,
    MediaPlayerEntityFeature,
    MediaPlayerState,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import (
    CoordinatorEntity,
    DataUpdateCoordinator,
)
import homeassistant.util.dt as dt_util

from .const import (
    ATTR_PLAYBACK_RATE,
    DOMAIN,
    EXPECTED_HEARTBEAT_FREQUENCY,
    LOGGER as _LOGGER,
)

PLATFORM = "media_player"

SUPPORTED_MINIMAL = (
    MediaPlayerEntityFeature.PAUSE
    | MediaPlayerEntityFeature.PLAY
    | MediaPlayerEntityFeature.STOP
)
SUPPORTED_TURN_OFF = MediaPlayerEntityFeature.TURN_OFF
SUPPORTED_TURN_ON = MediaPlayerEntityFeature.TURN_ON

# Enable to remove clones (second / third, nth instances)
# of any player when the player exits.  Not enabled by
# default because events in the logbook disappear when
# the player goes away.
# Clones are always removed upon start or reload of the
# integration, since there is no value in keeping them
# around.
REMOVE_CLONES_WHILE_RUNNING = True


def _get_player_id(
    entity: er.RegistryEntry,
) -> str:
    return entity.unique_id.split("-", 1)[1]


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up all the media players for the MPRIS integration."""
    # Suppress circular import induced by merging media_player_entity_manager.py
    # into media_player.py.  HassmprisData refers to MPRISCoordinator
    # and async_setup_entry refers to HassmprisData.
    from .models import HassmprisData  # pylint: disable=import-outside-toplevel

    component_data = cast(
        HassmprisData,
        hass.data[DOMAIN][config_entry.entry_id],
    )
    mpris_client = component_data.client
    manager = MPRISCoordinator(
        hass,
        config_entry,
        mpris_client,
        async_add_entities,
    )
    await manager.start()
    component_data.entity_manager = manager

    async def _async_stop_manager(*unused_args: Any) -> None:
        # The following is a very simple trick to delete the
        # reference to the manager once the manager is stopped
        # once via this mechanism.
        # That way, if the manager is stopped because the entry
        # was unloaded (e.g. integration deleted), this will
        # not try to stop the manager again.
        if component_data.entity_manager:
            _LOGGER.debug("Stopping entity manager")
            await component_data.entity_manager.stop()
            _LOGGER.debug("Entity manager stopped")
            component_data.entity_manager = None

    component_data.unloaders.append(_async_stop_manager)


class HASSMPRISEntity(CoordinatorEntity, MediaPlayerEntity):
    """Represents an MPRIS media player entity."""

    _attr_device_class = MediaPlayerDeviceClass.TV
    _attr_supported_features = SUPPORTED_MINIMAL
    _attr_playback_rate: float = 1.0
    _attr_should_poll: bool = False
    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: MPRISCoordinator,
        integration_id: str,
        player_id: str,
    ) -> None:
        """Initialize the entity.

        Arguments:
          coordinator: the coordinator handling this entity
          integration_id: unique identifier of the integration
          player_id: the name / unique identifier of the player
          initial_state: the (optional) initial state of the entity
        """
        super().__init__(coordinator)
        self.coordinator = coordinator
        self.player_id = player_id
        self._integration_id = integration_id
        self._attr_available = True
        self._metadata: dict[str, Any] = {}

    @callback
    def _handle_coordinator_update(self) -> None:
        if self.player_id not in self.coordinator.data:
            # This player has been removed.  Ignore this.
            return

        data = self.coordinator.data[self.player_id]

        updated = False

        if "available" in data:
            if self._attr_available != data["available"]:
                _LOGGER.debug(
                    "%s: Updating availability from %s to %s",
                    self.name,
                    self._attr_available,
                    data["available"],
                )
                self._attr_available = data["available"]
                if not self._attr_available:
                    self._attr_state = MediaPlayerState.OFF
                updated = True
                del data["available"]

        if "state" in data:
            if self._attr_state != data["state"]:
                from_playing_to_paused = (
                    self._attr_state == MediaPlayerState.PLAYING
                    and data["state"] == MediaPlayerState.PAUSED
                )
                _LOGGER.debug(
                    "%s: Updating state from %s to %s",
                    self.name,
                    self._attr_state,
                    data["state"],
                )
                self._attr_state = data["state"]
                if (
                    from_playing_to_paused
                    and self._attr_media_position_updated_at is not None
                    and self._attr_media_position is not None
                ):
                    elapsed = dt_util.utcnow() - self._attr_media_position_updated_at
                    self._attr_media_position += round(
                        self._attr_playback_rate * elapsed.total_seconds()
                    )
                    self._attr_media_position_updated_at = dt_util.utcnow()
                    _LOGGER.debug(
                        "%s: Artificially setting media position to %s",
                        self.name,
                        self._attr_media_position,
                    )
                updated = True
            del data["state"]

        if "metadata" in data:
            if self._metadata != data["metadata"]:
                _LOGGER.debug("%s: Updating metadata", self.name)
                self._metadata = data["metadata"]
                if "mpris:length" in data["metadata"]:
                    length: int | None = round(
                        float(self._metadata["mpris:length"]) / 1000 / 1000
                    )
                    if length is not None and length <= 0:
                        length = None
                else:
                    length = None
                self._attr_media_duration = length
                _LOGGER.debug(
                    "%s: Setting media duration to %s",
                    self.name,
                    self._attr_media_duration,
                )
                updated = True
            del data["metadata"]

        if "position" in data:
            new_position = None if data["position"] is None else round(data["position"])
            if self._attr_media_duration is None:
                if self._attr_media_position is not None:
                    # Media duration is None, position must be forced to None.
                    _LOGGER.debug("%s: Nullifying media position", self.name)
                    self._attr_media_position = None
            elif self._attr_media_position != new_position:
                # Media duration is known, and position has changed.
                self._attr_media_position = (
                    new_position if new_position is not None else None
                )
                _LOGGER.debug(
                    "%s: Setting media position to %s",
                    self.name,
                    self._attr_media_position,
                )
            # We update the time that the position update was sent
            # from the server, so that UI can keep accurate track
            # of where the play head is.  Think of someone seeking
            # to second 33 of a music track twice in a row.  If we
            # did not update this timestamp, then the play head UI
            # shows would be in second 66.
            self._attr_media_position_updated_at = dt_util.utcnow()
            updated = True
            del data["position"]

        if "mpris_properties" in data:
            updated = self._update_mpris_properties(data["mpris_properties"]) or updated
            del data["mpris_properties"]

        if updated:
            self.async_write_ha_state()

    def _update_mpris_properties(
        self,
        props: mpris_pb2.MPRISPlayerProperties,
    ) -> bool:
        """Update player properties based on incoming MPRISPlayerProperties."""

        feats = self._attr_supported_features
        if props.HasField("CanControl"):
            if not props.CanControl:
                feats = cast(MediaPlayerEntityFeature, 0)
            else:
                feats = SUPPORTED_MINIMAL

        update_state = False

        for name, bitwisefield in {
            "CanPlay": MediaPlayerEntityFeature.PLAY,
            "CanPause": MediaPlayerEntityFeature.PAUSE,
            "CanSeek": MediaPlayerEntityFeature.SEEK,
            "CanGoNext": MediaPlayerEntityFeature.NEXT_TRACK,
            "CanGoPrevious": MediaPlayerEntityFeature.PREVIOUS_TRACK,
        }.items():
            if props.HasField(name):
                val = getattr(props, name)
                if val:
                    feats = feats | bitwisefield
                else:
                    feats = feats & ~bitwisefield

        if feats != self._attr_supported_features:
            _LOGGER.debug(
                "%s: new feature bitfield: %s",
                self.name,
                feats,
            )
            self._attr_supported_features = feats
            update_state = True

        if props.HasField("Rate") and props.Rate != self._attr_playback_rate:
            _LOGGER.debug("%s: new rate: %s", self.name, props.Rate)
            self._attr_playback_rate = props.Rate
            update_state = True

        return update_state

    @property
    def unique_id(self) -> str:
        """Return the unique ID of this entity."""
        return self._integration_id + "-" + self.player_id

    @property
    def name(self) -> str:
        """Return the name of the entity."""
        assert self.player_id
        return self.player_id

    @property
    def device_info(self) -> DeviceInfo:
        """Return the device information associated with the entity."""
        return DeviceInfo(
            identifiers={(DOMAIN, self._integration_id)},
            name=f"MPRIS agent at {self.coordinator.client.host}",
            manufacturer="Freedesktop",
        )

    async def async_added_to_hass(self) -> None:
        """Entity has been added to HASS."""
        _LOGGER.debug("Added: %s", self.name)
        await super().async_added_to_hass()
        self._handle_coordinator_update()

    async def async_will_remove_from_hass(self) -> None:
        """Entity is about to be removed from HASS."""
        _LOGGER.debug("Will remove: %s", self.name)
        await super().async_will_remove_from_hass()

    async def async_media_play(self) -> None:
        """Begin playback."""
        try:
            _LOGGER.debug("%s: play", self.name)
            await self.coordinator.client.play(self.player_id)
        except Exception as exc:
            raise HomeAssistantError("cannot play: %s" % exc) from exc

    async def async_media_pause(self) -> None:
        """Pause playback."""
        try:
            _LOGGER.debug("%s: pause", self.name)
            await self.coordinator.client.pause(self.player_id)
        except Exception as exc:
            raise HomeAssistantError("cannot pause: %s" % exc) from exc

    async def async_media_stop(self) -> None:
        """Stop playback."""
        try:
            _LOGGER.debug("%s: stop", self.name)
            await self.coordinator.client.stop(self.player_id)
        except Exception as exc:
            raise HomeAssistantError("cannot stop: %s" % exc) from exc

    async def async_media_next_track(self) -> None:
        """Skip to next track."""
        try:
            _LOGGER.debug("%s: next track", self.name)
            await self.coordinator.client.next(self.player_id)
        except Exception as exc:
            raise HomeAssistantError("cannot next: %s" % exc) from exc

    async def async_media_previous_track(self) -> None:
        """Skip to previous track."""
        try:
            _LOGGER.debug("%s: previous track", self.name)
            await self.coordinator.client.previous(self.player_id)
        except Exception as exc:
            raise HomeAssistantError("cannot previous: %s" % exc) from exc

    async def async_media_seek(self, position: float) -> None:
        """Send seek command."""
        try:
            _LOGGER.debug("%s: seeking to %s", self.name, position)
            trackid = self._metadata.get("mpris:trackid", None)
            await self.coordinator.client.set_position(
                self.player_id,
                trackid,
                position,
            )
        except Exception as exc:
            raise HomeAssistantError("cannot seek: %s" % exc) from exc

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return entity specific state attributes."""
        if self.state == MediaPlayerState.OFF:
            return {}
        return {ATTR_PLAYBACK_RATE: self._attr_playback_rate}


class MPRISCoordinatorUpdate(TypedDict):
    """The type of update sent through MPRISCoordinator.data to entities."""

    available: NotRequired[bool]
    state: NotRequired[MediaPlayerState]
    metadata: NotRequired[dict[str, Any]]
    mpris_properties: NotRequired[mpris_pb2.MPRISPlayerProperties]
    position: NotRequired[float | None]


class MPRISCoordinator(DataUpdateCoordinator):
    """The entity manager manages MPRIS media player entities.

    This class is responsible for maintaining the known player entities
    in sync with the state as reported by the server, as well as keeping
    tabs of newly-appeared players and players that have gone.
    """

    config_entry: ConfigEntry

    def __init__(
        self,
        hass: HomeAssistant,
        config_entry: ConfigEntry,
        mpris_client: hassmpris_client.AsyncMPRISClient,
        async_add_entities: AddEntitiesCallback,
    ) -> None:
        """Initialize the entity manager.

        Arguments:
          hass: the HomeAssistant singleton
          config_entry: the configuration entry associated with
                        this component (or integration?)
          mpris_client: the MPRIS client endpoint object
          async_add_entities: callback to add entities async
        """
        super().__init__(hass, _LOGGER, name="MPRIS")
        self.data: dict[str, MPRISCoordinatorUpdate] = {}
        self.config_entry = config_entry
        self.async_add_entities = async_add_entities
        self._client = mpris_client
        self._shutdown: asyncio.Future[bool] = asyncio.Future()
        self._started = False

    @property
    def client(self) -> hassmpris_client.AsyncMPRISClient:
        """Return the MPRIS client associated with this entity manager."""
        return self._client

    async def start(self) -> None:
        """Start the entity manager as a separate task."""
        self.hass.loop.create_task(self.run())

    async def run(self) -> None:
        """Run the entity manager."""
        if self._started:
            _LOGGER.debug("Thread already started")
            return
        self._started = True
        _LOGGER.debug("Streaming updates started")
        seen_excs: dict[Any, bool] = {}
        while not self._shutdown.done():
            try:
                cycle_update_count = 0
                try:
                    async for _ in self._monitor_updates():
                        cycle_update_count = cycle_update_count + 1
                        seen_excs = {}
                except Exception as exc:
                    if self._shutdown.done():
                        _LOGGER.debug("Ignoring %s since we are shut down", exc)
                        await self._shutdown
                        continue
                    raise
            except hassmpris_client.Unauthenticated:
                _LOGGER.error(
                    "We have been deauthorized after %s updates -- no further updates "
                    "will occur until reauthentication",
                    cycle_update_count,
                )
                self.config_entry.async_start_reauth(self.hass)
                await self.stop()
            except hassmpris_client.ClientException as exc:
                lg = _LOGGER.exception if type(exc) not in seen_excs else _LOGGER.debug
                seen_excs[type(exc)] = True
                lg(
                    "We lost connectivity after %s updates (%s) -- reconnecting",
                    cycle_update_count,
                    exc,
                )
                await asyncio.sleep(5)
            except Exception as exc:  # pylint: disable=broad-exception-caught
                lg = _LOGGER.exception if type(exc) not in seen_excs else _LOGGER.debug
                seen_excs[type(exc)] = True
                lg(
                    "Unexpected exception after %s updates (%s) -- reconnecting",
                    cycle_update_count,
                    exc,
                )
                await asyncio.sleep(5)
        await self._shutdown
        _LOGGER.debug("Streaming updates ended")

    async def stop(
        self,
        *unused_args: Any,
        exception: Exception | None = None,
    ) -> None:
        """Stop the loop."""
        try:
            if exception:
                _LOGGER.debug("Exceptional stop: %s", exception)
                self._shutdown.set_exception(exception)
            else:
                _LOGGER.debug("Normal stop")
                self._shutdown.set_result(True)
        except asyncio.InvalidStateError:
            pass

    def _mark_all_entities_unavailable(self) -> None:
        for player_id in self.data:
            self.data[player_id]["available"] = False

    def _mark_all_entities_available(self) -> None:
        for player_id in self.data:
            self.data[player_id]["available"] = True

    async def _monitor_updates(self) -> AsyncGenerator[None, None]:
        """Obtain a real-time feed of player updates."""
        try:
            started_syncing = False
            finished_syncing = False
            async for update in self.client.stream_updates(
                timeout=round(EXPECTED_HEARTBEAT_FREQUENCY * 1.5)
            ):
                if not started_syncing:
                    # First update.  Mark entities available.  This does not
                    # mark players as off or idle or any other state — that
                    # happens below in _handle_update() and then at the end
                    # in _finish_initial_players_sync() for all entities that
                    # did not get corresponding updates from the server.
                    started_syncing = True
                if update.HasField("player"):
                    # There's a player update incoming.
                    updated = self._handle_update(update.player)
                    if finished_syncing and updated:
                        self.async_set_updated_data(self.data)
                elif not finished_syncing:
                    # Ah, this is the signal that all players known to the agent
                    # have had their information sent to Home Assistant.
                    self._add_players_not_running()
                    self._mark_all_entities_available()
                    finished_syncing = True
                    self.async_set_updated_data(self.data)
                yield
        finally:
            # Whether due to error or request, we no longer get updates.
            # All entities are now unavailable from the standpoint of the
            # HASS MPRIS client.
            if started_syncing:
                # The loop synced entities successfully at least once
                # Time to mark any available entities as unavailable.
                self._mark_all_entities_unavailable()
                self.async_set_updated_data(self.data)

    def _handle_update(
        self,
        discovery_data: mpris_pb2.MPRISUpdateReply,
    ) -> bool:
        """Handle a single player update."""
        _LOGGER.debug("Handling update:")
        for line in f"{discovery_data}".splitlines():
            _LOGGER.debug("  %s", line)
        state = MediaPlayerState.IDLE
        player_id = discovery_data.player_id
        updated = False

        if player_id not in self.data:
            _LOGGER.debug("Adding player %s", player_id)
            entity = HASSMPRISEntity(
                self,
                self.config_entry.entry_id,
                player_id,
            )
            self.data[player_id] = {"available": True}
            self.async_add_entities([entity])
            updated = True

        table = {
            mpris_pb2.PlayerStatus.GONE: MediaPlayerState.OFF,
            mpris_pb2.PlayerStatus.APPEARED: MediaPlayerState.IDLE,
            mpris_pb2.PlayerStatus.PLAYING: MediaPlayerState.PLAYING,
            mpris_pb2.PlayerStatus.PAUSED: MediaPlayerState.PAUSED,
            mpris_pb2.PlayerStatus.STOPPED: MediaPlayerState.IDLE,
        }
        if discovery_data.status != mpris_pb2.PlayerStatus.UNKNOWN:
            state = table[discovery_data.status]
            _LOGGER.debug("New state of player %s: %s", player_id, state)
            self.data[player_id]["state"] = state
            updated = True

        if discovery_data.json_metadata:
            metadata = json.loads(discovery_data.json_metadata)
            self.data[player_id]["metadata"] = metadata
            updated = True

        if discovery_data.HasField("properties"):
            mpris_properties = discovery_data.properties
            self.data[player_id]["mpris_properties"] = mpris_properties
            updated = True

        if discovery_data.HasField("seeked"):
            position = discovery_data.seeked.position
            self.data[player_id]["position"] = position
            updated = True

        if self._should_remove(player_id) and state == MediaPlayerState.OFF:
            for entry in self._player_registry_entries(player_id):
                _LOGGER.debug("Removing player %s from registry", player_id)
                er.async_get(self.hass).async_remove(entry.entity_id)
                del self.data[player_id]
                return False

        return updated

    def _player_registry_entries(
        self, player_id: str | None = None
    ) -> list[er.RegistryEntry]:
        reg = er.async_get(self.hass)
        return [
            e
            for e in reg.entities.values()
            if e.config_entry_id == self.config_entry.entry_id
            and (player_id is None or _get_player_id(e) == player_id)
        ]

    def _should_remove(self, player_id: str) -> bool:
        name_without_2 = re.sub(" [(][0-9+][)]$", "", player_id)
        return (
            name_without_2 != player_id
            and name_without_2 in self.data
            and REMOVE_CLONES_WHILE_RUNNING
        )

    def _add_players_not_running(self) -> None:
        for entry in self._player_registry_entries():
            player_id = _get_player_id(entry)
            if player_id not in self.data:
                if self._should_remove(player_id):
                    _LOGGER.debug("Removing player %s from registry", player_id)
                    er.async_get(self.hass).async_remove(entry.entity_id)
                    del self.data[player_id]
                else:
                    _LOGGER.debug("Resuscitating player %s", player_id)
                    entity = HASSMPRISEntity(
                        self,
                        self.config_entry.entry_id,
                        player_id,
                    )
                    self.data[player_id] = {
                        "available": True,
                        "state": MediaPlayerState.OFF,
                    }
                    self.async_add_entities([entity])
