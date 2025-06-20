"""Support for Songpal-enabled (Sony) switches."""

from __future__ import annotations

import logging
from typing import Any

from songpal import SongpalException

from homeassistant.components.switch import SwitchEntity
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
        hass, entry, SongpalSwitchEntity, "booleanTarget", async_add_entities
    )


class SongpalSwitchEntity(SongpalSettingEntity, SwitchEntity):
    """Defines a Songpal switch."""

    @property
    def is_on(self) -> bool | None:
        """Return the state of the switch."""

        if not self.setting:
            return None

        return self.setting.currentValue == "on"

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn off setting."""
        try:
            await self.coordinator.get_setting_setter(self._setting_bank)(
                self._setting_target, "off"
            )
        except SongpalException as e:
            _LOGGER.debug(e)

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn on setting."""
        try:
            await self.coordinator.get_setting_setter(self._setting_bank)(
                self._setting_target, "on"
            )
        except SongpalException as e:
            _LOGGER.debug(e)
