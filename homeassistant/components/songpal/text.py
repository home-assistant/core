"""Support for Songpal-enabled (Sony) switches."""

from __future__ import annotations

import logging

from songpal import SongpalException

from homeassistant.components.text import TextEntity
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
        hass, entry, SongpalStringEntity, "stringTarget", async_add_entities
    )


class SongpalStringEntity(SongpalSettingEntity, TextEntity):
    """Defines a Songpal string entity."""

    @property
    def native_value(self) -> str | None:
        """Get the current string."""

        if not self.setting:
            return None

        return self.setting.currentValue

    async def async_set_value(self, value: str) -> None:
        """Change the string."""

        try:
            await self.coordinator.set_setting(
                self._setting_bank, self._setting_target, value
            )
        except SongpalException as e:
            _LOGGER.debug(e)
