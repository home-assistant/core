"""Support for Songpal-enabled (Sony) switches."""

from __future__ import annotations

from typing import Any

from homeassistant.components.switch import DOMAIN as SWITCH_DOMAIN, SwitchEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .entities import create_entities_for_platform
from .entity import SongpalSettingEntity


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up songpal coordinator and entities."""

    create_entities_for_platform(
        hass, entry, SongpalSwitchEntity, SWITCH_DOMAIN, async_add_entities
    )


class SongpalSwitchEntity(SongpalSettingEntity, SwitchEntity):
    """Defines a Songpal switch."""

    @property
    def is_on(self) -> bool | None:
        """Return the state of the switch."""
        for setting in self.coordinator.data[self._setting_bank]:
            if setting.target == self._setting_name:
                break
        else:
            return None

        return setting.currentValue == "on"

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn off setting."""
        await self.coordinator.get_setting_setter(self._setting_bank)(
            self._setting_name, "off"
        )

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn on setting."""
        await self.coordinator.get_setting_setter(self._setting_bank)(
            self._setting_name, "on"
        )
