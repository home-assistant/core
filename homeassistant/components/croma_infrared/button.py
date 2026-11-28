"""Button platform for the Croma Infrared integration.

Commands the media player has no slot for. Power is here too: it sends the
toggle without touching the media player's assumed state, so a TV switched with
its own remote can be brought back in step.
"""

from dataclasses import dataclass
from typing import override

from infrared_protocols.codes.croma.tv import CromaTVCode

from homeassistant.components.button import ButtonEntity, ButtonEntityDescription
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import CONF_INFRARED_EMITTER_ENTITY_ID
from .entity import CromaIrEntity

PARALLEL_UPDATES = 1


@dataclass(frozen=True, kw_only=True)
class CromaIrButtonEntityDescription(ButtonEntityDescription):
    """Describes a Croma IR button entity."""

    command_code: CromaTVCode


BUTTON_DESCRIPTIONS: tuple[CromaIrButtonEntityDescription, ...] = (
    CromaIrButtonEntityDescription(
        key="power", translation_key="power", command_code=CromaTVCode.POWER
    ),
    CromaIrButtonEntityDescription(
        key="up", translation_key="up", command_code=CromaTVCode.UP
    ),
    CromaIrButtonEntityDescription(
        key="down", translation_key="down", command_code=CromaTVCode.DOWN
    ),
    CromaIrButtonEntityDescription(
        key="left", translation_key="left", command_code=CromaTVCode.LEFT
    ),
    CromaIrButtonEntityDescription(
        key="right", translation_key="right", command_code=CromaTVCode.RIGHT
    ),
    CromaIrButtonEntityDescription(
        key="ok", translation_key="ok", command_code=CromaTVCode.OK
    ),
    CromaIrButtonEntityDescription(
        key="back", translation_key="back", command_code=CromaTVCode.BACK
    ),
    CromaIrButtonEntityDescription(
        key="exit", translation_key="exit", command_code=CromaTVCode.EXIT
    ),
    CromaIrButtonEntityDescription(
        key="home", translation_key="home", command_code=CromaTVCode.HOME
    ),
    CromaIrButtonEntityDescription(
        key="menu", translation_key="menu", command_code=CromaTVCode.MENU
    ),
    CromaIrButtonEntityDescription(
        key="settings", translation_key="settings", command_code=CromaTVCode.SETTINGS
    ),
    CromaIrButtonEntityDescription(
        key="apps", translation_key="apps", command_code=CromaTVCode.APPS
    ),
    CromaIrButtonEntityDescription(
        key="input", translation_key="input", command_code=CromaTVCode.SOURCE
    ),
    CromaIrButtonEntityDescription(
        key="info", translation_key="info", command_code=CromaTVCode.INFO
    ),
    CromaIrButtonEntityDescription(
        key="guide", translation_key="guide", command_code=CromaTVCode.EPG
    ),
    CromaIrButtonEntityDescription(
        key="account", translation_key="account", command_code=CromaTVCode.ACCOUNT
    ),
    CromaIrButtonEntityDescription(
        key="voice", translation_key="voice", command_code=CromaTVCode.VOICE
    ),
    CromaIrButtonEntityDescription(
        key="subtitles",
        translation_key="subtitles",
        command_code=CromaTVCode.SUBTITLES,
    ),
    CromaIrButtonEntityDescription(
        key="program_up",
        translation_key="program_up",
        command_code=CromaTVCode.PROGRAM_UP,
    ),
    CromaIrButtonEntityDescription(
        key="program_down",
        translation_key="program_down",
        command_code=CromaTVCode.PROGRAM_DOWN,
    ),
    CromaIrButtonEntityDescription(
        key="fast_forward",
        translation_key="fast_forward",
        command_code=CromaTVCode.FAST_FORWARD,
    ),
    CromaIrButtonEntityDescription(
        key="rewind", translation_key="rewind", command_code=CromaTVCode.REWIND
    ),
    CromaIrButtonEntityDescription(
        key="free_hotkey",
        translation_key="free_hotkey",
        command_code=CromaTVCode.FREE_HOTKEY,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Croma IR buttons from a config entry."""
    infrared_entity_id = entry.data[CONF_INFRARED_EMITTER_ENTITY_ID]
    async_add_entities(
        CromaIrButton(entry, infrared_entity_id, description)
        for description in BUTTON_DESCRIPTIONS
    )


class CromaIrButton(CromaIrEntity, ButtonEntity):
    """Croma IR button entity."""

    entity_description: CromaIrButtonEntityDescription

    def __init__(
        self,
        entry: ConfigEntry,
        infrared_entity_id: str,
        description: CromaIrButtonEntityDescription,
    ) -> None:
        """Initialize Croma IR button."""
        super().__init__(entry, infrared_entity_id, unique_id_suffix=description.key)
        self.entity_description = description

    @override
    async def async_press(self) -> None:
        """Press the button."""
        await self._send_command(self.entity_description.command_code.to_command())
