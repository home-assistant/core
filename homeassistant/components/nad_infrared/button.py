"""Button platform for NAD Infrared integration."""

from dataclasses import dataclass
from typing import override

from infrared_protocols.codes.nad.amplifier import NADAmplifierCode
from infrared_protocols.codes.nad.cd import NADCDCode
from infrared_protocols.codes.nad.tape import NADTapeCode
from infrared_protocols.codes.nad.tuner import NADTunerCode

from homeassistant.components.button import ButtonEntity, ButtonEntityDescription
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import NadIrConfigEntry
from .const import CONF_DEVICE_TYPE, NADDeviceType
from .entity import NADCode, NadIrEntity

PARALLEL_UPDATES = 1


@dataclass(frozen=True, kw_only=True)
class NadIrButtonEntityDescription(ButtonEntityDescription):
    """Describes NAD Infrared button entity."""

    command_code: NADCode


AMPLIFIER_BUTTONS: tuple[NadIrButtonEntityDescription, ...] = (
    NadIrButtonEntityDescription(
        key="cursor_up",
        translation_key="cursor_up",
        command_code=NADAmplifierCode.CURSOR_UP,
    ),
    NadIrButtonEntityDescription(
        key="cursor_down",
        translation_key="cursor_down",
        command_code=NADAmplifierCode.CURSOR_DOWN,
    ),
    NadIrButtonEntityDescription(
        key="cursor_left",
        translation_key="cursor_left",
        command_code=NADAmplifierCode.CURSOR_LEFT,
    ),
    NadIrButtonEntityDescription(
        key="cursor_right",
        translation_key="cursor_right",
        command_code=NADAmplifierCode.CURSOR_RIGHT,
    ),
    NadIrButtonEntityDescription(
        key="enter", translation_key="enter", command_code=NADAmplifierCode.ENTER
    ),
    NadIrButtonEntityDescription(
        key="menu", translation_key="menu", command_code=NADAmplifierCode.MENU
    ),
    NadIrButtonEntityDescription(
        key="source_up",
        translation_key="source_up",
        command_code=NADAmplifierCode.SOURCE_UP,
    ),
    NadIrButtonEntityDescription(
        key="source_down",
        translation_key="source_down",
        command_code=NADAmplifierCode.SOURCE_DOWN,
    ),
    NadIrButtonEntityDescription(
        key="av_preset_1",
        translation_key="av_preset_1",
        command_code=NADAmplifierCode.AV_PRESET_1,
    ),
    NadIrButtonEntityDescription(
        key="av_preset_2",
        translation_key="av_preset_2",
        command_code=NADAmplifierCode.AV_PRESET_2,
    ),
    NadIrButtonEntityDescription(
        key="av_preset_3",
        translation_key="av_preset_3",
        command_code=NADAmplifierCode.AV_PRESET_3,
    ),
    NadIrButtonEntityDescription(
        key="av_preset_4",
        translation_key="av_preset_4",
        command_code=NADAmplifierCode.AV_PRESET_4,
    ),
    NadIrButtonEntityDescription(
        key="av_preset_5",
        translation_key="av_preset_5",
        command_code=NADAmplifierCode.AV_PRESET_5,
    ),
    NadIrButtonEntityDescription(
        key="surround_mode",
        translation_key="surround_mode",
        command_code=NADAmplifierCode.SURROUND_MODE,
    ),
    NadIrButtonEntityDescription(
        key="audyssey",
        translation_key="audyssey",
        command_code=NADAmplifierCode.AUDYSSEY,
    ),
    NadIrButtonEntityDescription(
        key="late_night",
        translation_key="late_night",
        command_code=NADAmplifierCode.LATE_NIGHT,
    ),
    NadIrButtonEntityDescription(
        key="tone_defeat",
        translation_key="tone_defeat",
        command_code=NADAmplifierCode.TONE_DEFEAT,
    ),
    NadIrButtonEntityDescription(
        key="speaker_a",
        translation_key="speaker_a",
        command_code=NADAmplifierCode.SPEAKER_A,
    ),
    NadIrButtonEntityDescription(
        key="speaker_b",
        translation_key="speaker_b",
        command_code=NADAmplifierCode.SPEAKER_B,
    ),
    NadIrButtonEntityDescription(
        key="center_volume_up",
        translation_key="center_volume_up",
        command_code=NADAmplifierCode.CENTER_VOLUME_UP,
    ),
    NadIrButtonEntityDescription(
        key="center_volume_down",
        translation_key="center_volume_down",
        command_code=NADAmplifierCode.CENTER_VOLUME_DOWN,
    ),
    NadIrButtonEntityDescription(
        key="surround_volume_up",
        translation_key="surround_volume_up",
        command_code=NADAmplifierCode.SURROUND_VOLUME_UP,
    ),
    NadIrButtonEntityDescription(
        key="surround_volume_down",
        translation_key="surround_volume_down",
        command_code=NADAmplifierCode.SURROUND_VOLUME_DOWN,
    ),
    NadIrButtonEntityDescription(
        key="sub_volume_up",
        translation_key="sub_volume_up",
        command_code=NADAmplifierCode.SUB_VOLUME_UP,
    ),
    NadIrButtonEntityDescription(
        key="sub_volume_down",
        translation_key="sub_volume_down",
        command_code=NADAmplifierCode.SUB_VOLUME_DOWN,
    ),
    NadIrButtonEntityDescription(
        key="display", translation_key="display", command_code=NADAmplifierCode.DISPLAY
    ),
    NadIrButtonEntityDescription(
        key="dimmer", translation_key="dimmer", command_code=NADAmplifierCode.DIMMER
    ),
    NadIrButtonEntityDescription(
        key="sleep", translation_key="sleep", command_code=NADAmplifierCode.SLEEP
    ),
    NadIrButtonEntityDescription(
        key="test_tone",
        translation_key="test_tone",
        command_code=NADAmplifierCode.TEST,
        entity_category=EntityCategory.CONFIG,
    ),
)

TUNER_BUTTONS: tuple[NadIrButtonEntityDescription, ...] = (
    NadIrButtonEntityDescription(
        key="tuner_am", translation_key="tuner_am", command_code=NADTunerCode.AM
    ),
    NadIrButtonEntityDescription(
        key="tuner_fm", translation_key="tuner_fm", command_code=NADTunerCode.FM
    ),
    NadIrButtonEntityDescription(
        key="tuner_dab", translation_key="tuner_dab", command_code=NADTunerCode.DAB
    ),
    NadIrButtonEntityDescription(
        key="tuner_mode", translation_key="tuner_mode", command_code=NADTunerCode.MODE
    ),
    NadIrButtonEntityDescription(
        key="tuner_tune_up",
        translation_key="tuner_tune_up",
        command_code=NADTunerCode.TUNE_UP,
    ),
    NadIrButtonEntityDescription(
        key="tuner_tune_down",
        translation_key="tuner_tune_down",
        command_code=NADTunerCode.TUNE_DOWN,
    ),
    NadIrButtonEntityDescription(
        key="tuner_search_up",
        translation_key="tuner_search_up",
        command_code=NADTunerCode.SEARCH_UP,
    ),
    NadIrButtonEntityDescription(
        key="tuner_search_down",
        translation_key="tuner_search_down",
        command_code=NADTunerCode.SEARCH_DOWN,
    ),
    NadIrButtonEntityDescription(
        key="tuner_preset_up",
        translation_key="tuner_preset_up",
        command_code=NADTunerCode.PRESET_UP,
    ),
    NadIrButtonEntityDescription(
        key="tuner_preset_down",
        translation_key="tuner_preset_down",
        command_code=NADTunerCode.PRESET_DOWN,
    ),
    NadIrButtonEntityDescription(
        key="tuner_preset_tune",
        translation_key="tuner_preset_tune",
        command_code=NADTunerCode.PRESET_TUNE,
    ),
    NadIrButtonEntityDescription(
        key="tuner_memory",
        translation_key="tuner_memory",
        command_code=NADTunerCode.MEMORY,
    ),
    NadIrButtonEntityDescription(
        key="tuner_delete",
        translation_key="tuner_delete",
        command_code=NADTunerCode.DELETE,
    ),
    NadIrButtonEntityDescription(
        key="tuner_bank", translation_key="tuner_bank", command_code=NADTunerCode.BANK
    ),
    NadIrButtonEntityDescription(
        key="tuner_blend",
        translation_key="tuner_blend",
        command_code=NADTunerCode.BLEND,
    ),
    NadIrButtonEntityDescription(
        key="tuner_enter",
        translation_key="tuner_enter",
        command_code=NADTunerCode.ENTER,
    ),
    NadIrButtonEntityDescription(
        key="tuner_number_0",
        translation_key="tuner_number_0",
        command_code=NADTunerCode.NUM_0,
        entity_registry_enabled_default=False,
    ),
    NadIrButtonEntityDescription(
        key="tuner_number_1",
        translation_key="tuner_number_1",
        command_code=NADTunerCode.NUM_1,
        entity_registry_enabled_default=False,
    ),
    NadIrButtonEntityDescription(
        key="tuner_number_2",
        translation_key="tuner_number_2",
        command_code=NADTunerCode.NUM_2,
        entity_registry_enabled_default=False,
    ),
    NadIrButtonEntityDescription(
        key="tuner_number_3",
        translation_key="tuner_number_3",
        command_code=NADTunerCode.NUM_3,
        entity_registry_enabled_default=False,
    ),
    NadIrButtonEntityDescription(
        key="tuner_number_4",
        translation_key="tuner_number_4",
        command_code=NADTunerCode.NUM_4,
        entity_registry_enabled_default=False,
    ),
    NadIrButtonEntityDescription(
        key="tuner_number_5",
        translation_key="tuner_number_5",
        command_code=NADTunerCode.NUM_5,
        entity_registry_enabled_default=False,
    ),
    NadIrButtonEntityDescription(
        key="tuner_number_6",
        translation_key="tuner_number_6",
        command_code=NADTunerCode.NUM_6,
        entity_registry_enabled_default=False,
    ),
    NadIrButtonEntityDescription(
        key="tuner_number_7",
        translation_key="tuner_number_7",
        command_code=NADTunerCode.NUM_7,
        entity_registry_enabled_default=False,
    ),
    NadIrButtonEntityDescription(
        key="tuner_number_8",
        translation_key="tuner_number_8",
        command_code=NADTunerCode.NUM_8,
        entity_registry_enabled_default=False,
    ),
    NadIrButtonEntityDescription(
        key="tuner_number_9",
        translation_key="tuner_number_9",
        command_code=NADTunerCode.NUM_9,
        entity_registry_enabled_default=False,
    ),
    NadIrButtonEntityDescription(
        key="tuner_number_10",
        translation_key="tuner_number_10",
        command_code=NADTunerCode.NUM_10,
        entity_registry_enabled_default=False,
    ),
    NadIrButtonEntityDescription(
        key="tuner_plus_10",
        translation_key="tuner_plus_10",
        command_code=NADTunerCode.PLUS_10,
        entity_registry_enabled_default=False,
    ),
)

CD_PLAYER_BUTTONS: tuple[NadIrButtonEntityDescription, ...] = (
    NadIrButtonEntityDescription(
        key="repeat", translation_key="repeat", command_code=NADCDCode.REPEAT
    ),
    NadIrButtonEntityDescription(
        key="random", translation_key="random", command_code=NADCDCode.RANDOM
    ),
    NadIrButtonEntityDescription(
        key="time", translation_key="time", command_code=NADCDCode.TIME
    ),
    NadIrButtonEntityDescription(
        key="scan_back", translation_key="scan_back", command_code=NADCDCode.SCAN_BACK
    ),
    NadIrButtonEntityDescription(
        key="scan_forward",
        translation_key="scan_forward",
        command_code=NADCDCode.SCAN_FORWARD,
    ),
    NadIrButtonEntityDescription(
        key="open_close",
        translation_key="open_close",
        command_code=NADCDCode.OPEN_CLOSE,
    ),
    NadIrButtonEntityDescription(
        key="next_disc",
        translation_key="next_disc",
        command_code=NADCDCode.NEXT_DISC,
        entity_registry_enabled_default=False,
    ),
    NadIrButtonEntityDescription(
        key="disc_1",
        translation_key="disc_1",
        command_code=NADCDCode.DISC_1,
        entity_registry_enabled_default=False,
    ),
    NadIrButtonEntityDescription(
        key="disc_2",
        translation_key="disc_2",
        command_code=NADCDCode.DISC_2,
        entity_registry_enabled_default=False,
    ),
    NadIrButtonEntityDescription(
        key="disc_3",
        translation_key="disc_3",
        command_code=NADCDCode.DISC_3,
        entity_registry_enabled_default=False,
    ),
    NadIrButtonEntityDescription(
        key="disc_4",
        translation_key="disc_4",
        command_code=NADCDCode.DISC_4,
        entity_registry_enabled_default=False,
    ),
    NadIrButtonEntityDescription(
        key="disc_5",
        translation_key="disc_5",
        command_code=NADCDCode.DISC_5,
        entity_registry_enabled_default=False,
    ),
)

TAPE_DECK_BUTTONS: tuple[NadIrButtonEntityDescription, ...] = (
    NadIrButtonEntityDescription(
        key="deck_a_play",
        translation_key="deck_a_play",
        command_code=NADTapeCode.DECK_A_PLAY,
    ),
    NadIrButtonEntityDescription(
        key="deck_a_reverse_play",
        translation_key="deck_a_reverse_play",
        command_code=NADTapeCode.DECK_A_REVERSE_PLAY,
    ),
    NadIrButtonEntityDescription(
        key="deck_a_stop",
        translation_key="deck_a_stop",
        command_code=NADTapeCode.DECK_A_STOP,
    ),
    NadIrButtonEntityDescription(
        key="deck_a_fast_forward",
        translation_key="deck_a_fast_forward",
        command_code=NADTapeCode.DECK_A_FAST_FORWARD,
    ),
    NadIrButtonEntityDescription(
        key="deck_a_rewind",
        translation_key="deck_a_rewind",
        command_code=NADTapeCode.DECK_A_REWIND,
    ),
    NadIrButtonEntityDescription(
        key="deck_a_record",
        translation_key="deck_a_record",
        command_code=NADTapeCode.DECK_A_RECORD,
    ),
    NadIrButtonEntityDescription(
        key="deck_b_play",
        translation_key="deck_b_play",
        command_code=NADTapeCode.DECK_B_PLAY,
    ),
    NadIrButtonEntityDescription(
        key="deck_b_reverse_play",
        translation_key="deck_b_reverse_play",
        command_code=NADTapeCode.DECK_B_REVERSE_PLAY,
    ),
    NadIrButtonEntityDescription(
        key="deck_b_stop",
        translation_key="deck_b_stop",
        command_code=NADTapeCode.DECK_B_STOP,
    ),
    NadIrButtonEntityDescription(
        key="deck_b_fast_forward",
        translation_key="deck_b_fast_forward",
        command_code=NADTapeCode.DECK_B_FAST_FORWARD,
    ),
    NadIrButtonEntityDescription(
        key="deck_b_rewind",
        translation_key="deck_b_rewind",
        command_code=NADTapeCode.DECK_B_REWIND,
    ),
    NadIrButtonEntityDescription(
        key="deck_b_record",
        translation_key="deck_b_record",
        command_code=NADTapeCode.DECK_B_RECORD,
    ),
    NadIrButtonEntityDescription(
        key="deck_b_pause",
        translation_key="deck_b_pause",
        command_code=NADTapeCode.DECK_B_PAUSE,
    ),
)

DEVICE_BUTTONS: dict[NADDeviceType, tuple[NadIrButtonEntityDescription, ...]] = {
    NADDeviceType.RECEIVER: AMPLIFIER_BUTTONS + TUNER_BUTTONS,
    NADDeviceType.AMPLIFIER: AMPLIFIER_BUTTONS,
    NADDeviceType.TUNER: TUNER_BUTTONS,
    NADDeviceType.CD_PLAYER: CD_PLAYER_BUTTONS,
    NADDeviceType.TAPE_DECK: TAPE_DECK_BUTTONS,
}


async def async_setup_entry(
    hass: HomeAssistant,
    entry: NadIrConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up NAD Infrared buttons from config entry."""
    async_add_entities(
        NadIrButton(entry, description)
        for description in DEVICE_BUTTONS[entry.data[CONF_DEVICE_TYPE]]
    )


class NadIrButton(NadIrEntity, ButtonEntity):
    """NAD Infrared button entity."""

    entity_description: NadIrButtonEntityDescription

    def __init__(
        self, entry: NadIrConfigEntry, description: NadIrButtonEntityDescription
    ) -> None:
        """Initialize NAD Infrared button."""
        super().__init__(entry, unique_id_suffix=description.key)
        self.entity_description = description

    @override
    async def async_press(self) -> None:
        """Press the button."""
        await self._send_nad_command(self.entity_description.command_code)
