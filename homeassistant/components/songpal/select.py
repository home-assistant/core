"""Support for Songpal-enabled (Sony) switches."""

from __future__ import annotations

import logging

from songpal import SongpalException
from songpal.containers import SettingCandidate

from homeassistant.components.select import SelectEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .entities import create_settings_entities_for_type
from .entity import SongpalSettingEntity

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up songpal coordinator and entities."""

    create_settings_entities_for_type(
        hass, entry, SongpalSelectEntity, "enumTarget", async_add_entities
    )


class SongpalSelectEntity(SongpalSettingEntity, SelectEntity):
    """Defines a Songpal switch."""

    @property
    def options(self) -> list[str]:
        """Return available options."""

        if not self.setting:
            return []

        setting_candidates: list[SettingCandidate] = self.setting.candidate

        setting_friendly_names: list[str] = [
            candidate.title for candidate in setting_candidates
        ]

        return setting_friendly_names

    @property
    def current_option(self) -> str | None:
        """Return currently selected option."""

        if not self.setting:
            return None

        for candidate in self.setting.candidate:
            if candidate.value == self.setting.currentValue:
                return candidate.title

        return None

    async def async_select_option(self, option: str) -> None:
        """Change the selected option."""

        if not self.setting:
            return

        for candidate in self.setting.candidate:
            if candidate.title == option:
                break
        else:
            return

        try:
            await self.coordinator.get_setting_setter(self._setting_bank)(
                self._setting_target, candidate.value
            )
        except SongpalException as e:
            _LOGGER.debug(e)
