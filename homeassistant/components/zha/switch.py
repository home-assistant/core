"""Switches on Zigbee Home Automation networks."""

from __future__ import annotations

import logging
from typing import Any

from homeassistant.components.switch import SwitchEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .entity import ZHAEntity
from .helpers import get_zha_data

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the Zigbee Home Automation switch from config entry."""
    zha_data = get_zha_data(hass)
    entities_to_create = zha_data.platforms.pop(Platform.SWITCH, [])
    async_add_entities(entities_to_create)


class Switch(ZHAEntity, SwitchEntity):
    """ZHA switch."""

    @property
    def is_on(self) -> bool:
        """Return if the switch is on based on the statemachine."""
        return self.entity_data.entity.is_on

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the entity on."""
        await self.entity_data.entity.async_turn_on(**kwargs)
        self.async_write_ha_state()

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the entity off."""
        await self.entity_data.entity.async_turn_off(**kwargs)
        self.async_write_ha_state()
