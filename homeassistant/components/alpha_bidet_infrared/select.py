"""Select platform for the Alpha Bidet Infrared integration."""

from dataclasses import dataclass
from typing import override

from infrared_protocols.codes.alpha_bidet.jx2 import AlphaBidetJX2Setting
from infrared_protocols.codes.alpha_bidet.models import (
    MODEL_TO_COMMAND_SET,
    AlphaBidetCommandSet,
    AlphaBidetModel,
)

from homeassistant.components.select import SelectEntity, SelectEntityDescription
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_MODEL
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.restore_state import RestoreEntity

from .entity import AlphaBidetIrEntity

PARALLEL_UPDATES = 1

# The remote sends the level itself rather than a step, so each option maps to one.
LEVELS: dict[str, int] = {"off": 0, "low": 1, "medium": 2, "high": 3}


@dataclass(frozen=True, kw_only=True)
class AlphaBidetIrSelectEntityDescription(SelectEntityDescription):
    """Describes an Alpha Bidet IR select entity."""

    setting: AlphaBidetJX2Setting


COMMAND_SET_SELECTS: dict[
    AlphaBidetCommandSet, tuple[AlphaBidetIrSelectEntityDescription, ...]
] = {
    AlphaBidetCommandSet.JX2: (
        AlphaBidetIrSelectEntityDescription(
            key="water_temperature",
            translation_key="water_temperature",
            options=list(LEVELS),
            setting=AlphaBidetJX2Setting.WATER_TEMP,
        ),
        AlphaBidetIrSelectEntityDescription(
            key="seat_temperature",
            translation_key="seat_temperature",
            options=list(LEVELS),
            setting=AlphaBidetJX2Setting.SEAT_TEMP,
        ),
    ),
}


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Alpha Bidet IR selects from a config entry."""
    command_set = MODEL_TO_COMMAND_SET[AlphaBidetModel(entry.data[CONF_MODEL])]
    async_add_entities(
        AlphaBidetIrSelect(entry, description)
        for description in COMMAND_SET_SELECTS[command_set]
    )


class AlphaBidetIrSelect(AlphaBidetIrEntity, SelectEntity, RestoreEntity):
    """Alpha Bidet IR select entity for a setting sent as an absolute level."""

    _attr_assumed_state = True
    entity_description: AlphaBidetIrSelectEntityDescription

    def __init__(
        self, entry: ConfigEntry, description: AlphaBidetIrSelectEntityDescription
    ) -> None:
        """Initialize Alpha Bidet IR select."""
        super().__init__(entry, unique_id_suffix=description.key)
        self.entity_description = description

    @override
    async def async_added_to_hass(self) -> None:
        """Restore the assumed level, as infrared cannot read it back from the bidet."""
        await super().async_added_to_hass()
        last_state = await self.async_get_last_state()
        if last_state is not None and last_state.state in LEVELS:
            self._attr_current_option = last_state.state

    @override
    async def async_select_option(self, option: str) -> None:
        """Send the chosen level."""
        await self._send_command(
            self.entity_description.setting.to_command(LEVELS[option])
        )
        self._attr_current_option = option
        self.async_write_ha_state()
