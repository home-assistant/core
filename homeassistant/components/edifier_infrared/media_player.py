"""Media player platform for Edifier infrared integration."""

from typing import override

from infrared_protocols.codes.edifier.models import EdifierCommandSet, EdifierModel
from infrared_protocols.codes.edifier.r1280db import EdifierR1280DBCode
from infrared_protocols.codes.edifier.r1280t import EdifierR1280TCode
from infrared_protocols.codes.edifier.r1700bt import EdifierR1700BTCode
from infrared_protocols.codes.edifier.rc20g import EdifierRC20GCode
from infrared_protocols.codes.edifier.s360db import EdifierS360DBCode
from infrared_protocols.codes.edifier.s3000pro import EdifierS3000ProCode

from homeassistant.components.infrared import InfraredEmitterConsumerEntity
from homeassistant.components.media_player import (
    MediaPlayerDeviceClass,
    MediaPlayerEntity,
    MediaPlayerEntityFeature,
    MediaPlayerState,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_MODEL
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import CONF_COMMAND_SET, CONF_INFRARED_ENTITY_ID, EdifierCode
from .entity import EdifierIrEntity

PARALLEL_UPDATES = 1


COMMAND_SET_COMMANDS: dict[
    EdifierCommandSet,
    dict[
        MediaPlayerEntityFeature,
        tuple[EdifierCode | tuple[EdifierCode, ...], ...],
    ],
] = {
    EdifierCommandSet.R1700BT: {
        MediaPlayerEntityFeature.TURN_ON: (EdifierR1700BTCode.POWER,),
        MediaPlayerEntityFeature.TURN_OFF: (EdifierR1700BTCode.POWER,),
        MediaPlayerEntityFeature.VOLUME_STEP: (
            (EdifierR1700BTCode.VOLUME_UP,),
            (EdifierR1700BTCode.VOLUME_DOWN,),
        ),
        MediaPlayerEntityFeature.VOLUME_MUTE: (EdifierR1700BTCode.MUTE,),
        MediaPlayerEntityFeature.PLAY: (EdifierR1700BTCode.PLAY_PAUSE,),
        MediaPlayerEntityFeature.PAUSE: (EdifierR1700BTCode.PLAY_PAUSE,),
        MediaPlayerEntityFeature.NEXT_TRACK: (EdifierR1700BTCode.FORWARD,),
        MediaPlayerEntityFeature.PREVIOUS_TRACK: (EdifierR1700BTCode.BACK,),
    },
    EdifierCommandSet.R1280DB: {
        MediaPlayerEntityFeature.TURN_ON: (EdifierR1280DBCode.POWER,),
        MediaPlayerEntityFeature.TURN_OFF: (EdifierR1280DBCode.POWER,),
        MediaPlayerEntityFeature.VOLUME_STEP: (
            (EdifierR1280DBCode.VOLUME_UP,),
            (EdifierR1280DBCode.VOLUME_DOWN,),
        ),
        MediaPlayerEntityFeature.VOLUME_MUTE: (EdifierR1280DBCode.MUTE,),
        MediaPlayerEntityFeature.PLAY: (EdifierR1280DBCode.PLAY_PAUSE,),
        MediaPlayerEntityFeature.PAUSE: (EdifierR1280DBCode.PLAY_PAUSE,),
        MediaPlayerEntityFeature.NEXT_TRACK: (EdifierR1280DBCode.FORWARD,),
        MediaPlayerEntityFeature.PREVIOUS_TRACK: (EdifierR1280DBCode.BACK,),
    },
    EdifierCommandSet.R1280T: {
        MediaPlayerEntityFeature.VOLUME_STEP: (
            (EdifierR1280TCode.VOLUME_UP,),
            (EdifierR1280TCode.VOLUME_DOWN,),
        ),
        MediaPlayerEntityFeature.VOLUME_MUTE: (EdifierR1280TCode.MUTE,),
    },
    EdifierCommandSet.S360DB: {
        MediaPlayerEntityFeature.TURN_ON: (EdifierS360DBCode.POWER,),
        MediaPlayerEntityFeature.TURN_OFF: (EdifierS360DBCode.POWER,),
        MediaPlayerEntityFeature.VOLUME_STEP: (
            (EdifierS360DBCode.VOLUME_UP,),
            (EdifierS360DBCode.VOLUME_DOWN,),
        ),
        MediaPlayerEntityFeature.PLAY: (EdifierS360DBCode.PLAY_PAUSE,),
        MediaPlayerEntityFeature.PAUSE: (EdifierS360DBCode.PLAY_PAUSE,),
        MediaPlayerEntityFeature.NEXT_TRACK: (EdifierS360DBCode.NEXT,),
        MediaPlayerEntityFeature.PREVIOUS_TRACK: (EdifierS360DBCode.PREVIOUS,),
    },
    EdifierCommandSet.RC20G: {
        MediaPlayerEntityFeature.TURN_ON: (EdifierRC20GCode.POWER,),
        MediaPlayerEntityFeature.TURN_OFF: (EdifierRC20GCode.POWER,),
        MediaPlayerEntityFeature.VOLUME_STEP: (
            (EdifierRC20GCode.VOLUME_UP_LEFT, EdifierRC20GCode.VOLUME_UP_RIGHT),
            (EdifierRC20GCode.VOLUME_DOWN_LEFT, EdifierRC20GCode.VOLUME_DOWN_RIGHT),
        ),
        MediaPlayerEntityFeature.VOLUME_MUTE: (EdifierRC20GCode.MUTE,),
        MediaPlayerEntityFeature.PLAY: (EdifierRC20GCode.PLAY_PAUSE,),
        MediaPlayerEntityFeature.PAUSE: (EdifierRC20GCode.PLAY_PAUSE,),
        MediaPlayerEntityFeature.NEXT_TRACK: (EdifierRC20GCode.FORWARD,),
        MediaPlayerEntityFeature.PREVIOUS_TRACK: (EdifierRC20GCode.PREVIOUS,),
    },
    EdifierCommandSet.S3000PRO: {
        MediaPlayerEntityFeature.TURN_ON: (EdifierS3000ProCode.POWER,),
        MediaPlayerEntityFeature.TURN_OFF: (EdifierS3000ProCode.POWER,),
        MediaPlayerEntityFeature.VOLUME_STEP: (
            (EdifierS3000ProCode.VOLUME_UP,),
            (EdifierS3000ProCode.VOLUME_DOWN,),
        ),
        MediaPlayerEntityFeature.VOLUME_MUTE: (EdifierS3000ProCode.MUTE,),
        MediaPlayerEntityFeature.PLAY: (EdifierS3000ProCode.PLAY_PAUSE,),
        MediaPlayerEntityFeature.PAUSE: (EdifierS3000ProCode.PLAY_PAUSE,),
        MediaPlayerEntityFeature.NEXT_TRACK: (EdifierS3000ProCode.NEXT,),
        MediaPlayerEntityFeature.PREVIOUS_TRACK: (EdifierS3000ProCode.PREVIOUS,),
    },
}


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Edifier IR media player."""
    infrared_entity_id = entry.data[CONF_INFRARED_ENTITY_ID]
    command_set = EdifierCommandSet(entry.data[CONF_COMMAND_SET])
    model = EdifierModel(entry.data[CONF_MODEL])
    async_add_entities(
        [EdifierIrMediaPlayer(entry, model, infrared_entity_id, command_set)]
    )


class EdifierIrMediaPlayer(
    EdifierIrEntity, InfraredEmitterConsumerEntity, MediaPlayerEntity
):
    """Edifier IR media player entity."""

    _attr_name = None
    _attr_assumed_state = True
    _attr_device_class = MediaPlayerDeviceClass.SPEAKER

    def __init__(
        self,
        entry: ConfigEntry,
        model: EdifierModel,
        infrared_entity_id: str,
        command_set: EdifierCommandSet,
    ) -> None:
        """Initialize Edifier IR media player."""
        super().__init__(entry, model, unique_id_suffix="media_player")
        self._infrared_emitter_entity_id = infrared_entity_id
        self._commands = COMMAND_SET_COMMANDS[command_set]
        self._attr_state = MediaPlayerState.ON
        self._attr_supported_features = MediaPlayerEntityFeature(0)
        for feature in self._commands:
            self._attr_supported_features |= feature

    async def _send_codes(self, *codes: EdifierCode) -> None:
        """Send one or more IR commands."""
        for code in codes:
            await self._send_command(code.to_command())

    @override
    async def async_turn_on(self) -> None:
        """Turn on the speaker."""
        await self._send_codes(*self._commands[MediaPlayerEntityFeature.TURN_ON])

    @override
    async def async_turn_off(self) -> None:
        """Turn off the speaker."""
        await self._send_codes(*self._commands[MediaPlayerEntityFeature.TURN_OFF])

    @override
    async def async_volume_up(self) -> None:
        """Send volume up command."""
        await self._send_codes(*self._commands[MediaPlayerEntityFeature.VOLUME_STEP][0])

    @override
    async def async_volume_down(self) -> None:
        """Send volume down command."""
        await self._send_codes(*self._commands[MediaPlayerEntityFeature.VOLUME_STEP][1])

    @override
    async def async_mute_volume(self, mute: bool) -> None:
        """Send mute command."""
        await self._send_codes(*self._commands[MediaPlayerEntityFeature.VOLUME_MUTE])

    @override
    async def async_media_play(self) -> None:
        """Send play command."""
        await self._send_codes(*self._commands[MediaPlayerEntityFeature.PLAY])

    @override
    async def async_media_pause(self) -> None:
        """Send pause command."""
        await self._send_codes(*self._commands[MediaPlayerEntityFeature.PAUSE])

    @override
    async def async_media_next_track(self) -> None:
        """Send next track command."""
        await self._send_codes(*self._commands[MediaPlayerEntityFeature.NEXT_TRACK])

    @override
    async def async_media_previous_track(self) -> None:
        """Send previous track command."""
        await self._send_codes(*self._commands[MediaPlayerEntityFeature.PREVIOUS_TRACK])
