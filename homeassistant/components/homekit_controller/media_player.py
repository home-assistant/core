"""Support for HomeKit Controller Televisions."""
from __future__ import annotations

import logging

from aiohomekit.model.characteristics import (
    CharacteristicsTypes,
    CurrentMediaStateValues,
    RemoteKeyValues,
    TargetMediaStateValues,
)
from aiohomekit.model.services import Service, ServicesTypes
from aiohomekit.utils import clamp_enum_to_char

from homeassistant.components.media_player import (
    MediaPlayerDeviceClass,
    MediaPlayerEntity,
    MediaPlayerEntityFeature,
    MediaPlayerState,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import KNOWN_DEVICES
from .entity import HomeKitEntity

_LOGGER = logging.getLogger(__name__)


HK_TO_HA_STATE = {
    CurrentMediaStateValues.PLAYING: MediaPlayerState.PLAYING,
    CurrentMediaStateValues.PAUSED: MediaPlayerState.PAUSED,
    CurrentMediaStateValues.STOPPED: MediaPlayerState.IDLE,
}


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Homekit television."""
    hkid = config_entry.data["AccessoryPairingID"]
    conn = hass.data[KNOWN_DEVICES][hkid]

    @callback
    def async_add_service(service: Service) -> bool:
        if service.type != ServicesTypes.TELEVISION:
            return False
        info = {"aid": service.accessory.aid, "iid": service.iid}
        async_add_entities([HomeKitTelevision(conn, info)], True)
        return True

    conn.add_listener(async_add_service)


class HomeKitTelevision(HomeKitEntity, MediaPlayerEntity):
    """Representation of a HomeKit Controller Television."""

    _attr_device_class = MediaPlayerDeviceClass.TV

    def get_characteristic_types(self) -> list[str]:
        """Define the homekit characteristics the entity cares about."""
        return [
            CharacteristicsTypes.ACTIVE,
            CharacteristicsTypes.CURRENT_MEDIA_STATE,
            CharacteristicsTypes.TARGET_MEDIA_STATE,
            CharacteristicsTypes.REMOTE_KEY,
            CharacteristicsTypes.ACTIVE_IDENTIFIER,
            # Characterics that are on the linked INPUT_SOURCE services
            CharacteristicsTypes.CONFIGURED_NAME,
            CharacteristicsTypes.IDENTIFIER,
        ]

    @property
    def supported_features(self) -> int:
        """Flag media player features that are supported."""
        features = 0

        if self.service.has(CharacteristicsTypes.ACTIVE_IDENTIFIER):
            features |= MediaPlayerEntityFeature.SELECT_SOURCE

        if self.service.has(CharacteristicsTypes.TARGET_MEDIA_STATE):
            if TargetMediaStateValues.PAUSE in self.supported_media_states:
                features |= MediaPlayerEntityFeature.PAUSE

            if TargetMediaStateValues.PLAY in self.supported_media_states:
                features |= MediaPlayerEntityFeature.PLAY

            if TargetMediaStateValues.STOP in self.supported_media_states:
                features |= MediaPlayerEntityFeature.STOP

        if (
            self.service.has(CharacteristicsTypes.REMOTE_KEY)
            and RemoteKeyValues.PLAY_PAUSE in self.supported_remote_keys
        ):
            features |= MediaPlayerEntityFeature.PAUSE | MediaPlayerEntityFeature.PLAY

        return features

    @property
    def supported_media_states(self) -> set[TargetMediaStateValues]:
        """Mediate state flags that are supported."""
        if not self.service.has(CharacteristicsTypes.TARGET_MEDIA_STATE):
            return set()

        return clamp_enum_to_char(
            TargetMediaStateValues,
            self.service[CharacteristicsTypes.TARGET_MEDIA_STATE],
        )

    @property
    def supported_remote_keys(self) -> set[int]:
        """Remote key buttons that are supported."""
        if not self.service.has(CharacteristicsTypes.REMOTE_KEY):
            return set()

        return clamp_enum_to_char(
            RemoteKeyValues, self.service[CharacteristicsTypes.REMOTE_KEY]
        )

    @property
    def source_list(self) -> list[str]:
        """List of all input sources for this television."""
        sources = []

        this_accessory = self._accessory.entity_map.aid(self._aid)
        this_tv = this_accessory.services.iid(self._iid)

        input_sources = this_accessory.services.filter(
            service_type=ServicesTypes.INPUT_SOURCE,
            parent_service=this_tv,
        )

        for input_source in input_sources:
            char = input_source[CharacteristicsTypes.CONFIGURED_NAME]
            sources.append(char.value)
        return sources

    @property
    def source(self) -> str | None:
        """Name of the current input source."""
        active_identifier = self.service.value(CharacteristicsTypes.ACTIVE_IDENTIFIER)
        if not active_identifier:
            return None

        this_accessory = self._accessory.entity_map.aid(self._aid)
        this_tv = this_accessory.services.iid(self._iid)

        input_source = this_accessory.services.first(
            service_type=ServicesTypes.INPUT_SOURCE,
            characteristics={CharacteristicsTypes.IDENTIFIER: active_identifier},
            parent_service=this_tv,
        )
        char = input_source[CharacteristicsTypes.CONFIGURED_NAME]
        return char.value

    @property
    def state(self) -> MediaPlayerState:
        """State of the tv."""
        active = self.service.value(CharacteristicsTypes.ACTIVE)
        if not active:
            return MediaPlayerState.OFF

        homekit_state = self.service.value(CharacteristicsTypes.CURRENT_MEDIA_STATE)
        if homekit_state is not None:
            return HK_TO_HA_STATE.get(homekit_state, MediaPlayerState.ON)

        return MediaPlayerState.ON

    async def async_media_play(self) -> None:
        """Send play command."""
        if self.state == MediaPlayerState.PLAYING:
            _LOGGER.debug("Cannot play while already playing")
            return

        if TargetMediaStateValues.PLAY in self.supported_media_states:
            await self.async_put_characteristics(
                {CharacteristicsTypes.TARGET_MEDIA_STATE: TargetMediaStateValues.PLAY}
            )
        elif RemoteKeyValues.PLAY_PAUSE in self.supported_remote_keys:
            await self.async_put_characteristics(
                {CharacteristicsTypes.REMOTE_KEY: RemoteKeyValues.PLAY_PAUSE}
            )

    async def async_media_pause(self) -> None:
        """Send pause command."""
        if self.state == MediaPlayerState.PAUSED:
            _LOGGER.debug("Cannot pause while already paused")
            return

        if TargetMediaStateValues.PAUSE in self.supported_media_states:
            await self.async_put_characteristics(
                {CharacteristicsTypes.TARGET_MEDIA_STATE: TargetMediaStateValues.PAUSE}
            )
        elif RemoteKeyValues.PLAY_PAUSE in self.supported_remote_keys:
            await self.async_put_characteristics(
                {CharacteristicsTypes.REMOTE_KEY: RemoteKeyValues.PLAY_PAUSE}
            )

    async def async_media_stop(self) -> None:
        """Send stop command."""
        if self.state == MediaPlayerState.IDLE:
            _LOGGER.debug("Cannot stop when already idle")
            return

        if TargetMediaStateValues.STOP in self.supported_media_states:
            await self.async_put_characteristics(
                {CharacteristicsTypes.TARGET_MEDIA_STATE: TargetMediaStateValues.STOP}
            )

    async def async_select_source(self, source: str) -> None:
        """Switch to a different media source."""
        this_accessory = self._accessory.entity_map.aid(self._aid)
        this_tv = this_accessory.services.iid(self._iid)

        input_source = this_accessory.services.first(
            service_type=ServicesTypes.INPUT_SOURCE,
            characteristics={CharacteristicsTypes.CONFIGURED_NAME: source},
            parent_service=this_tv,
        )

        if not input_source:
            raise ValueError(f"Could not find source {source}")

        identifier = input_source[CharacteristicsTypes.IDENTIFIER]

        await self.async_put_characteristics(
            {CharacteristicsTypes.ACTIVE_IDENTIFIER: identifier.value}
        )
