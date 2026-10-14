"""Button platform for the Persang Infrared integration.

Only commands the media player has no slot for live here: the mode and EQ
cycles, scan and repeat, and the numeric keypad.
"""

from dataclasses import dataclass
from typing import override

from infrared_protocols.codes.persang.speaker import PersangSpeakerCode

from homeassistant.components.button import ButtonEntity, ButtonEntityDescription
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import CONF_INFRARED_EMITTER_ENTITY_ID
from .entity import PersangIrEntity

PARALLEL_UPDATES = 1


@dataclass(frozen=True, kw_only=True)
class PersangIrButtonEntityDescription(ButtonEntityDescription):
    """Describes a Persang IR button entity."""

    command_code: PersangSpeakerCode


BUTTON_DESCRIPTIONS: tuple[PersangIrButtonEntityDescription, ...] = (
    PersangIrButtonEntityDescription(
        key="mode",
        translation_key="mode",
        command_code=PersangSpeakerCode.MODE,
    ),
    PersangIrButtonEntityDescription(
        key="eq",
        translation_key="eq",
        command_code=PersangSpeakerCode.EQ,
    ),
    PersangIrButtonEntityDescription(
        key="scan",
        translation_key="scan",
        command_code=PersangSpeakerCode.SCAN,
    ),
    PersangIrButtonEntityDescription(
        key="repeat",
        translation_key="repeat",
        command_code=PersangSpeakerCode.REPEAT,
    ),
    *(
        PersangIrButtonEntityDescription(
            key=f"num_{digit}",
            translation_key=f"num_{digit}",
            command_code=PersangSpeakerCode[f"NUM_{digit}"],
        )
        for digit in range(10)
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Persang IR buttons from a config entry."""
    infrared_entity_id = entry.data[CONF_INFRARED_EMITTER_ENTITY_ID]
    async_add_entities(
        PersangIrButton(entry, infrared_entity_id, description)
        for description in BUTTON_DESCRIPTIONS
    )


class PersangIrButton(PersangIrEntity, ButtonEntity):
    """Persang IR button entity."""

    entity_description: PersangIrButtonEntityDescription

    def __init__(
        self,
        entry: ConfigEntry,
        infrared_entity_id: str,
        description: PersangIrButtonEntityDescription,
    ) -> None:
        """Initialize Persang IR button."""
        super().__init__(entry, infrared_entity_id, unique_id_suffix=description.key)
        self.entity_description = description

    @override
    async def async_press(self) -> None:
        """Press the button."""
        await self._send_command(self.entity_description.command_code.to_command())
