"""Support for interfacing with the HASS MPRIS agent."""
from __future__ import annotations

import asyncio
import json
import re
from typing import Any, cast

from hassmpris.proto import mpris_pb2
import hassmpris_client
import voluptuous as vol

from homeassistant.components.media_player import (
    MediaPlayerDeviceClass,
    MediaPlayerEntity,
    MediaPlayerEntityFeature,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    EVENT_HOMEASSISTANT_STOP,
    STATE_IDLE,
    STATE_OFF,
    STATE_PAUSED,
    STATE_PLAYING,
    STATE_UNKNOWN,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_validation as cv, entity_registry as er
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
import homeassistant.util.dt as dt_util

from .const import DOMAIN, ENTRY_CLIENT, ENTRY_MANAGER, ENTRY_PLAYERS, LOGGER as _LOGGER

PLATFORM = "media_player"

DISCOVERY_SCHEMA = vol.Schema(
    {
        vol.Required("player_id"): cv.string,
    }
)

SUPPORTED_MINIMAL = (
    MediaPlayerEntityFeature.PAUSE
    | MediaPlayerEntityFeature.PLAY
    | MediaPlayerEntityFeature.STOP
)
SUPPORTED_TURN_OFF = MediaPlayerEntityFeature.TURN_OFF
SUPPORTED_TURN_ON = MediaPlayerEntityFeature.TURN_ON


def _feat2bitfield(bitfield: int, obj: object) -> str:
    fields = []
    for f in dir(obj):
        v = getattr(obj, f)
        if not isinstance(v, int):
            continue
        if bitfield & v:
            fields.append(f)
    return ",".join(fields)


class HASSMPRISEntity(MediaPlayerEntity):
    """This class represents an MPRIS media player entity."""

    _attr_device_class = MediaPlayerDeviceClass.TV
    _attr_supported_features = SUPPORTED_MINIMAL

    def __init__(
        self,
        client: hassmpris_client.AsyncMPRISClient,
        integration_id: str,
        player_id: str,
    ):
        """
        Initialize the entity.

        Parameters:
          client: the client to the remote agent
          integration_id: unique identifier of the integration
          player_id: the name / unique identifier of the player
        """
        super().__init__()
        if client is None:
            raise ValueError("Instantiation of this class requires a client")
        self.client: hassmpris_client.AsyncMPRISClient | None = client
        self._client_host = self.client.host
        self.player_id = player_id
        self._integration_id = integration_id
        self._attr_available = True
        self._metadata: dict[str, Any] = {}

    async def set_unavailable(self):
        """Mark player as unavailable."""
        _LOGGER.debug("Marking %s as unavailable" % self)
        self.client = None
        self._attr_available = False
        await self.update_state(STATE_UNKNOWN)

    async def async_removed_from_registry(self) -> None:
        """Clean up when removed from the registry."""
        self.client = None

    async def set_available(
        self,
        client: hassmpris_client.AsyncMPRISClient,
    ):
        """
        Mark a player as available again.

        Parameters:
          client: the new client to use to talk to the agent
        """
        _LOGGER.debug("Marking %s as available" % self)
        self.client = client
        self._client_host = self.client.host
        self._attr_available = True
        if self.hass:
            await self.async_update_ha_state(True)

    @property
    def unique_id(self) -> str:
        """Return the unique ID of this entity."""
        return self._integration_id + "-" + self.player_id

    @property
    def name(self):
        """Return the name of the entity."""
        return self.player_id

    @property
    def device_info(self) -> DeviceInfo:
        """Return the device information associated with the entity."""
        return DeviceInfo(
            identifiers={(DOMAIN, self._integration_id)},
            name="MPRIS agent at %s" % self._client_host,
            manufacturer="Freedesktop",
        )

    @property
    def should_poll(self) -> bool:
        """Do not poll."""
        return False

    @property
    def state(self):
        """Return the current playback state of the entity."""
        return self._attr_state

    @property
    def metadata(self) -> dict[str, Any]:
        """Return the metadata of the media playing right now."""
        # FIXME this is probably incorrect data type, we want
        # other information such as player playback length
        # and current position.
        return self._metadata

    @staticmethod
    def config_schema():
        """Return the discovery schema."""
        return DISCOVERY_SCHEMA

    async def async_media_play(self):
        """Begin playback."""
        if self.client:
            await self.client.play(self.player_id)

    async def async_media_pause(self):
        """Pause playback."""
        if self.client:
            await self.client.pause(self.player_id)

    async def async_media_stop(self):
        """Stop playback."""
        if self.client:
            await self.client.stop(self.player_id)

    async def async_media_next_track(self):
        """Skip to next track."""
        if self.client:
            await self.client.next(self.player_id)

    async def async_media_previous_track(self):
        """Skip to previous track."""
        if self.client:
            await self.client.previous(self.player_id)

    async def async_media_seek(self, position: float):
        """Send seek command."""
        if self.client:
            trackid = self._metadata.get("mpris:trackid")
            if trackid:
                await self.client.set_position(
                    self.player_id,
                    trackid,
                    position,
                )

    async def update_state(
        self,
        new_state: str,
    ):
        """Update player state based on reports from the server."""
        if new_state == self._attr_state:
            return

        _LOGGER.debug(
            "Updating state from %s to %s",
            self._attr_state,
            new_state,
        )
        self._attr_state = new_state
        if self.hass:
            await self.async_update_ha_state(True)

    async def update_metadata(self, new_metadata: dict[str, Any]):
        """Update player metadata based on incoming metadata (a dict)."""
        self._metadata = new_metadata
        if "mpris:length" in self._metadata:
            length: int | None = round(
                float(self._metadata["mpris:length"]) / 1000 / 1000
            )
            if length is not None and length <= 0:
                length = None
        else:
            length = None

        self._attr_media_duration = length
        self._attr_media_position = 0 if length is not None else None
        self._attr_media_position_updated_at = dt_util.utcnow()

        _LOGGER.debug("Setting media duration to %s", self._attr_media_duration)
        _LOGGER.debug("Setting media position to %s", self._attr_media_position)

        if self.hass:
            await self.async_update_ha_state(True)

    async def update_position(self, new_position: float):
        """Update position."""
        self._attr_media_position_updated_at = dt_util.utcnow()
        self._attr_media_position = (
            round(new_position) if new_position is not None else None
        )
        _LOGGER.debug("Setting media position to %s", self._attr_media_position)
        if self.hass:
            await self.async_update_ha_state(True)

    async def update_mpris_properties(
        self,
        p: mpris_pb2.MPRISPlayerProperties,
    ):
        """Update player properties based on incoming MPRISPlayerProperties."""
        feats = self._attr_supported_features
        if p.HasField("CanControl"):
            if not p.CanControl:
                feats = 0
            else:
                feats = SUPPORTED_MINIMAL

        for name, bitwisefield in {
            "CanPlay": MediaPlayerEntityFeature.PLAY,
            "CanPause": MediaPlayerEntityFeature.PAUSE,
            "CanSeek": MediaPlayerEntityFeature.SEEK,
            "CanGoNext": MediaPlayerEntityFeature.NEXT_TRACK,
            "CanGoPrevious": MediaPlayerEntityFeature.PREVIOUS_TRACK,
        }.items():
            if p.HasField(name):
                val = getattr(p, name)
                if val:
                    feats = feats | bitwisefield
                else:
                    feats = feats & ~bitwisefield

        _LOGGER.debug(
            "%s: current feature bitfield: (%s) %s",
            self.name,
            feats,
            _feat2bitfield(feats, MediaPlayerEntityFeature),
        )
        if feats != self._attr_supported_features:
            self._attr_supported_features = feats
            if self.hass:
                await self.async_update_ha_state(True)


class EntityManager:
    """
    The entity manager manages MPRIS media player entities.

    This class is responsible for maintaining the known player entities
    in sync with the state as reported by the server, as well as keeping
    tabs of newly-appeared players and players that have gone.
    """

    def __init__(
        self,
        hass: HomeAssistant,
        config_entry: ConfigEntry,
        async_add_entities: AddEntitiesCallback,
    ):
        """
        Initialize the entity manager.

        Parameters:
          hass: the HomeAssistant singleton
          config_entry: the configuration entry associated with
                        this component (or integration?)
          async_add_entities: callback to add entities async
        """
        self.hass = hass
        self.config_entry = config_entry
        self.config_entry_id = config_entry.entry_id
        self.async_add_entities = async_add_entities
        self.component_data = hass.data[DOMAIN][self.config_entry_id]
        self._shutdown: asyncio.Future[bool] = asyncio.Future()
        self._started = False
        _LOGGER.debug("Registering entity manager in integration data.")
        self.component_data[ENTRY_MANAGER] = self

    @property
    def players(self) -> dict[str, HASSMPRISEntity]:
        """Return the players known to this entity manager."""
        if ENTRY_PLAYERS not in self.component_data:
            self.component_data[ENTRY_PLAYERS] = {}
        return cast(dict[str, HASSMPRISEntity], self.component_data[ENTRY_PLAYERS])

    @property
    def client(self) -> hassmpris_client.AsyncMPRISClient:
        """Return the MPRIS client associated with this entity manager."""
        return self.component_data[ENTRY_CLIENT]

    async def start(self):
        """Start the entity manager as a separate task."""
        self.hass.loop.create_task(self.run())

    async def run(self):
        """Run the entity manager."""
        if self._started:
            _LOGGER.debug("Thread already started")
            return
        self._started = True
        _LOGGER.debug("Streaming updates started.")
        # FIXME upon disconnect or unauth update all known entities to off.
        while not self._shutdown.done():
            try:
                try:
                    await self._monitor_updates()
                except Exception as e:
                    if self._shutdown.done():
                        _LOGGER.debug("Ignoring %s since we are shut down.", e)
                        await self._shutdown
                        continue
                    raise
            except hassmpris_client.Unauthenticated:
                _LOGGER.warning(
                    "We have been deauthorized.  No further updates "
                    "will occur until reauthentication."
                )
                await self._mark_all_entities_unavailable()
                self.config_entry.async_start_reauth(self.hass)
                await self.stop()
            except hassmpris_client.ClientException as e:
                _LOGGER.warning("We lost connectivity (%s).  Reconnecting.", e)
                await self._mark_all_entities_unavailable()
                await asyncio.sleep(5)
            except Exception as e:
                await self.stop(exception=e)
        await self._shutdown
        _LOGGER.debug("Streaming updates ended.")

    async def stop(
        self,
        *unused_args: Any,
        exception: Exception | None = None,
    ):
        """Stop the loop."""
        try:
            if exception:
                self._shutdown.set_exception(exception)
            else:
                self._shutdown.set_result(True)
        except asyncio.InvalidStateError:
            pass

    async def _mark_all_entities_unavailable(self):
        for entity in self.players.values():
            await entity.set_unavailable()

    async def _mark_all_entities_available(self):
        for entity in self.players.values():
            await entity.set_available(self.client)

    async def _sync_entity_entries(self):
        reg = er.async_get(self.hass)

        def player_id_from_entity(entity: er.RegistryEntry) -> str:
            return entity.unique_id.split("-", 1)[1]

        def is_copy(player_id: str) -> bool:
            return bool(re.match(".* [(]\\d+[)]", player_id))

        def is_off(player: HASSMPRISEntity) -> bool:
            offstates = [STATE_OFF, STATE_UNKNOWN]
            return player.state in offstates

        def known(player_id: str) -> HASSMPRISEntity | None:
            return self.players.get(player_id)

        for entity in [
            e
            for e in reg.entities.values()
            if e.config_entry_id == self.config_entry_id
        ]:
            player_id = player_id_from_entity(entity)
            if is_copy(player_id):
                remove = True
                if player := known(player_id):
                    if is_off(player):
                        del self.players[player_id]
                    else:
                        # Player is not off.  Not removing.
                        remove = False
                if remove:
                    _LOGGER.debug("Removing copy %s" % player_id)
                    reg.async_remove(entity.entity_id)
            else:
                if not known(player_id):
                    _LOGGER.debug("Resuscitating known player %s" % player_id)
                    entity = HASSMPRISEntity(
                        self.client, self.config_entry_id, player_id
                    )
                    self.players[player_id] = entity
                    self.async_add_entities([entity])

    async def _monitor_updates(self):
        marked = False
        async for update in self.client.stream_updates():
            if not marked:
                await self._mark_all_entities_available()
            marked = True
            if update.HasField("player"):
                await self._handle_update(update.player)
            else:
                await self._sync_entity_entries()

    async def _handle_update(
        self,
        discovery_data: mpris_pb2.MPRISUpdateReply,
    ):
        _LOGGER.debug("Handling update: %s", discovery_data)
        state = STATE_IDLE
        fire_status_update_observed = False
        table = {
            mpris_pb2.PlayerStatus.GONE: STATE_OFF,
            mpris_pb2.PlayerStatus.APPEARED: STATE_IDLE,
            mpris_pb2.PlayerStatus.PLAYING: STATE_PLAYING,
            mpris_pb2.PlayerStatus.PAUSED: STATE_PAUSED,
            mpris_pb2.PlayerStatus.STOPPED: STATE_IDLE,
        }
        if discovery_data.status != mpris_pb2.PlayerStatus.UNKNOWN:
            try:
                state = table[discovery_data.status]
                fire_status_update_observed = True
            except Exception:
                _LOGGER.exception(
                    "Invalid state %s",
                    discovery_data.status,
                )

        fire_metadata_update_observed = False
        if discovery_data.json_metadata:
            fire_metadata_update_observed = True
            metadata = json.loads(discovery_data.json_metadata)

        fire_properties_update_observed = False
        if discovery_data.HasField("properties"):
            fire_properties_update_observed = True
            mpris_properties = discovery_data.properties
        fire_seeked_observed = False
        if discovery_data.HasField("seeked"):
            fire_seeked_observed = True
            position = discovery_data.seeked.position

        player_id = discovery_data.player_id

        if player_id in self.players:
            entity: HASSMPRISEntity = self.players[player_id]
        else:
            entity = HASSMPRISEntity(self.client, self.config_entry_id, player_id)
            self.async_add_entities([entity])
            self.players[player_id] = entity

        if fire_status_update_observed:
            await entity.update_state(state)
        if fire_metadata_update_observed:
            await entity.update_metadata(metadata)
        if fire_properties_update_observed:
            await entity.update_mpris_properties(mpris_properties)
        if fire_seeked_observed:
            await entity.update_position(position)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> bool:
    """Set up all the media players for the MPRIS integration."""
    manager = EntityManager(hass, config_entry, async_add_entities)
    hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STOP, manager.stop)
    await manager.start()
    return True
