"""Support for Songpal-enabled (Sony) switches."""

from __future__ import annotations

import logging

from songpal import SongpalException
from songpal.containers import SettingCandidate

from homeassistant.components.number import NumberEntity
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
        hass, entry, SongpalIntegerEntity, "integerTarget", async_add_entities
    )


class SongpalIntegerEntity(SongpalSettingEntity, NumberEntity):
    """Defines a Songpal integer."""

    def update_state(self, data) -> None:
        """Process updated state from coordinator."""
        super().update_state(data)

        if not self.setting:
            return

        if len(self.setting.candidate) == 1:
            candidate: SettingCandidate = self.setting.candidate[0]

            self._attr_native_min_value = candidate.min
            self._attr_native_max_value = candidate.max
            self._attr_native_step = candidate.step
        else:
            self._attr_native_min_value = 0
            self._attr_native_max_value = 100
            self._attr_native_step = 1

        self._attr_native_value = self.setting.currentValue

    async def async_set_native_value(self, value: float) -> None:
        """Change the number."""

        try:
            await self.coordinator.set_setting(
                self._setting_bank, self._setting_target, str(round(value))
            )
        except SongpalException as e:
            _LOGGER.debug(e)
