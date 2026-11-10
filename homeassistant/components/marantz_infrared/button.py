"""Button platform for Marantz IR integration.

Only commands that aren't already exposed by the media player live here:
speaker A/B, source-direct toggle, and loudness toggle.
"""

from dataclasses import dataclass
from typing import override

from infrared_protocols.codes.marantz.audio import MarantzAudioCode

from homeassistant.components.button import ButtonEntity, ButtonEntityDescription
from homeassistant.const import CONF_MODEL
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import MarantzIrConfigEntry
from .const import CONF_INFRARED_EMITTER_ENTITY_ID, MODELS
from .entity import MarantzIrEntity

PARALLEL_UPDATES = 1


@dataclass(frozen=True, kw_only=True)
class MarantzIrButtonEntityDescription(ButtonEntityDescription):
    """Describes Marantz IR button entity."""

    command_code: MarantzAudioCode


BUTTON_DESCRIPTIONS: tuple[MarantzIrButtonEntityDescription, ...] = (
    MarantzIrButtonEntityDescription(
        key="speaker_ab",
        translation_key="speaker_ab",
        command_code=MarantzAudioCode.SPEAKER_AB,
    ),
    MarantzIrButtonEntityDescription(
        key="speaker_a_off",
        translation_key="speaker_a_off",
        command_code=MarantzAudioCode.SPEAKER_A_OFF,
    ),
    MarantzIrButtonEntityDescription(
        key="speaker_a_on",
        translation_key="speaker_a_on",
        command_code=MarantzAudioCode.SPEAKER_A_ON,
    ),
    MarantzIrButtonEntityDescription(
        key="speaker_b_off",
        translation_key="speaker_b_off",
        command_code=MarantzAudioCode.SPEAKER_B_OFF,
    ),
    MarantzIrButtonEntityDescription(
        key="speaker_b_on",
        translation_key="speaker_b_on",
        command_code=MarantzAudioCode.SPEAKER_B_OFF,
    ),
    MarantzIrButtonEntityDescription(
        key="source_direct",
        translation_key="source_direct",
        command_code=MarantzAudioCode.SOURCE_DIRECT,
    ),
    MarantzIrButtonEntityDescription(
        key="loudness",
        translation_key="loudness",
        command_code=MarantzAudioCode.LOUDNESS,
    ),
    MarantzIrButtonEntityDescription(
        key="power_amp_direct_on",
        translation_key="power_amp_direct_on",
        command_code=MarantzAudioCode.POWER_AMP_DIRECT_ON,
    ),
    MarantzIrButtonEntityDescription(
        key="power_amp_direct_off",
        translation_key="power_amp_direct_off",
        command_code=MarantzAudioCode.POWER_AMP_DIRECT_OFF,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: MarantzIrConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Marantz IR buttons from config entry."""
    infrared_entity_id = entry.data[CONF_INFRARED_EMITTER_ENTITY_ID]
    model_codes = MODELS[entry.data[CONF_MODEL]].codes
    async_add_entities(
        MarantzIrButton(entry, infrared_entity_id, description)
        for description in BUTTON_DESCRIPTIONS
        if description.command_code in model_codes
    )


class MarantzIrButton(MarantzIrEntity, ButtonEntity):
    """Marantz IR button entity."""

    entity_description: MarantzIrButtonEntityDescription

    def __init__(
        self,
        entry: MarantzIrConfigEntry,
        infrared_entity_id: str,
        description: MarantzIrButtonEntityDescription,
    ) -> None:
        """Initialize Marantz IR button."""
        super().__init__(entry, infrared_entity_id, unique_id_suffix=description.key)
        self.entity_description = description

    @override
    async def async_press(self) -> None:
        """Press the button."""
        await self._send_marantz_command(self.entity_description.command_code)
