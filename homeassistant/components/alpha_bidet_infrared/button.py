"""Button platform for the Alpha Bidet Infrared integration."""

from dataclasses import dataclass
from typing import override

from infrared_protocols.codes.alpha_bidet.jx2 import AlphaBidetJX2Code
from infrared_protocols.codes.alpha_bidet.models import (
    MODEL_TO_COMMAND_SET,
    AlphaBidetCommandSet,
    AlphaBidetModel,
)

from homeassistant.components.button import ButtonEntity, ButtonEntityDescription
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_MODEL
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .entity import AlphaBidetIrEntity

PARALLEL_UPDATES = 1


@dataclass(frozen=True, kw_only=True)
class AlphaBidetIrButtonEntityDescription(ButtonEntityDescription):
    """Describes an Alpha Bidet IR button entity."""

    command_code: AlphaBidetJX2Code


COMMAND_SET_BUTTONS: dict[
    AlphaBidetCommandSet, tuple[AlphaBidetIrButtonEntityDescription, ...]
] = {
    AlphaBidetCommandSet.JX2: tuple(
        AlphaBidetIrButtonEntityDescription(
            key=code.name.lower(),
            translation_key=code.name.lower(),
            command_code=code,
        )
        for code in AlphaBidetJX2Code
    ),
}


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Alpha Bidet IR buttons from a config entry."""
    command_set = MODEL_TO_COMMAND_SET[AlphaBidetModel(entry.data[CONF_MODEL])]
    async_add_entities(
        AlphaBidetIrButton(entry, description)
        for description in COMMAND_SET_BUTTONS[command_set]
    )


class AlphaBidetIrButton(AlphaBidetIrEntity, ButtonEntity):
    """Alpha Bidet IR button entity."""

    entity_description: AlphaBidetIrButtonEntityDescription

    def __init__(
        self, entry: ConfigEntry, description: AlphaBidetIrButtonEntityDescription
    ) -> None:
        """Initialize Alpha Bidet IR button."""
        super().__init__(entry, unique_id_suffix=description.key)
        self.entity_description = description

    @override
    async def async_press(self) -> None:
        """Press the button."""
        await self._send_command(self.entity_description.command_code.to_command())
