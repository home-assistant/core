"""Support for interfacing with the HASS MPRIS agent."""
from __future__ import annotations

import asyncio
import json
import logging
import re
from typing import Any, Dict, Optional, cast

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

from .const import DOMAIN, ENTRY_CLIENT, ENTRY_PLAYERS, ENTRY_MANAGER

_LOGGER = logging.getLogger(__name__)

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
SUPPORTED_SEEK = MediaPlayerEntityFeature.SEEK


class HASSMPRISEntity(MediaPlayerEntity):

    # FIXME players already playing when HASSMPRIS starts
    # appear as idle and "cannot be made to play".
    _attr_device_class = MediaPlayerDeviceClass.TV

    _attr_supported_features = SUPPORTED_MINIMAL

    def __init__(
        self,
        client: hassmpris_client.AsyncMPRISClient,
        integration_id: str,
        player_id: str,
    ):
        super().__init__()
        if client is None:
            raise ValueError("Instantiation of this class requires a client")
        self.client: hassmpris_client.AsyncMPRISClient | None = client
        self._client_host = self.client.host
        self.player_id = player_id
        self._integration_id = integration_id
        self._attr_available = True
        self._state = STATE_OFF
        self._metadata: dict[str, Any] = {}

    async def set_unavailable(self):
        _LOGGER.debug("Marking %s as unavailable" % self)
        self.client = None
        self._attr_available = False
        await self.update_state(STATE_UNKNOWN)

    async def async_removed_from_registry(self) -> None:
        self.client = None

    async def set_available(
        self,
        client: hassmpris_client.AsyncMPRISClient,
    ):
        _LOGGER.debug("Marking %s as available" % self)
        self.client = client
        self._client_host = self.client.host
        self._attr_available = True
        await self.update_state(STATE_OFF)

    @property
    def unique_id(self) -> str:
        return self._integration_id + "-" + self.player_id

    @property
    def name(self):
        return self.player_id

    @property
    def device_info(self) -> DeviceInfo:
        return DeviceInfo(
            identifiers={(DOMAIN, self._integration_id)},
            name="MPRIS agent at %s" % self._client_host,
            manufacturer="Freedesktop",
        )

    @property
    def should_poll(self) -> bool:
        return False

    @property
    def state(self):
        return self._state

    @property
    def metadata(self) -> dict[str, Any]:
        # FIXME this is probably incorrect data type, we want
        # other information such as player playback length
        # and current position.
        return self._metadata

    @staticmethod
    def config_schema():
        return DISCOVERY_SCHEMA

    async def async_media_play(self):
        if self.client:
            await self.client.play(self.player_id)

    async def async_media_pause(self):
        if self.client:
            await self.client.pause(self.player_id)

    async def async_media_stop(self):
        if self.client:
            await self.client.stop(self.player_id)

    async def update_state(self, new_state):
        self._state = new_state
        if self.hass:
            await self.async_update_ha_state(True)

    async def update_metadata(self, new_metadata):
        self._metadata = new_metadata
        if self.hass:
            await self.async_update_ha_state(True)


class EntityManager:
    def __init__(
        self,
        hass: HomeAssistant,
        config_entry: ConfigEntry,
        async_add_entities: AddEntitiesCallback,
    ):
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
        if ENTRY_PLAYERS not in self.component_data:
            self.component_data[ENTRY_PLAYERS] = dict()
        return cast(dict[str, HASSMPRISEntity], self.component_data[ENTRY_PLAYERS])

    @property
    def client(self) -> hassmpris_client.AsyncMPRISClient:
        return self.component_data[ENTRY_CLIENT]

    async def start(self):
        self.hass.loop.create_task(self.run())

    async def run(self):
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
        exception: Optional[Exception] = None,
    ):
        """Stops the loop."""
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
        fire_metadata_update_observed = False
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
        if discovery_data.json_metadata:
            fire_metadata_update_observed = True
            metadata = json.loads(discovery_data.json_metadata)

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


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> bool:
    """Sets up all the media players for the MPRIS integration."""
    manager = EntityManager(hass, config_entry, async_add_entities)
    hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STOP, manager.stop)
    await manager.start()
    return True
