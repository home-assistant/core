"""Select platform for Songpal."""
from __future__ import annotations

import logging

from homeassistant.components.number import NumberEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from .coordinator import SongpalCoordinator
from .entity import SongpalSettingEntity
from .media_player import MEDIA_PLAYER_SETTINGS

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up songpal select entities."""
    coordinator: SongpalCoordinator = hass.data[DOMAIN][config_entry.entry_id]

    entities = []

    for setting in coordinator.settings_definitions:
        _LOGGER.debug("Looking at setting %r", setting)

        # Ignore settings that are exposed via MediaPlayerEntity.
        if setting.titleTextID in MEDIA_PLAYER_SETTINGS:
            continue

        if setting.type in {"integerTarget", "doubleNumberTarget"}:
            entities.append(SongpalNumberEntity(coordinator, setting))

    async_add_entities(entities)


class SongpalNumberEntity(NumberEntity, SongpalSettingEntity):
    """Base entity for Songpal number settings."""

    @property
    def value(self) -> float | None:
        """Return the current value for the setting."""
        if self._current_value is None:
            return None

        return float(self._current_value)

    @property
    def min_value(self) -> float:
        """Return the minimum value for the setting."""
        return float(self.candidates[0].min)

    @property
    def max_value(self) -> float:
        """Return the maximum value for the setting."""
        return float(self.candidates[0].max)

    @property
    def step(self) -> float:
        """Return the step for each change."""
        return float(self.candidates[0].step)

    async def async_set_value(self, value: float) -> None:
        """Change the set value."""
        if self._setting.type == "integerTarget":
            normalized_value = str(int(value))
        else:
            normalized_value = str(value)

        await self.update_setting(str(normalized_value))
