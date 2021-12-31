"""Select platform for Songpal."""
from __future__ import annotations

import logging

from homeassistant.components.select import SelectEntity
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

        if setting.type == "enumTarget":
            entities.append(SongpalSelectEntity(coordinator, setting))

    async_add_entities(entities)


class SongpalSelectEntity(SelectEntity, SongpalSettingEntity):
    """Base entity for Songpal enum settings."""

    @property
    def options(self) -> list[str]:
        """Return the list of available options for the setting."""
        return [
            candidate.title for candidate in self.candidates if candidate.isAvailable
        ]

    @property
    def current_option(self) -> str | None:
        """Return the current selected option, or none."""
        for candidate in self.candidates:
            if candidate.value == self._current_value:
                return candidate.title
        return None

    async def async_select_option(self, option: str) -> None:
        """Change the selected option."""
        for candidate in self.candidates:
            if candidate.title == option:
                await self.update_setting(candidate)
                break
        else:
            _LOGGER.warning(
                "Unable to select option '%s', no matching title found", option
            )
