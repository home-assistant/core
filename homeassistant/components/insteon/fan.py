"""Support for INSTEON fans via PowerLinc Modem."""

from __future__ import annotations

import math
from typing import Any

from homeassistant.components.fan import FanEntity, FanEntityFeature
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.util.percentage import (
    percentage_to_ranged_value,
    ranged_value_to_percentage,
)

from .const import SIGNAL_ADD_ENTITIES
from .insteon_entity import InsteonEntity
from .utils import async_add_insteon_devices, async_add_insteon_entities

SPEED_RANGE = (1, 255)  # off is not included


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the Insteon fans from a config entry."""

    @callback
    def async_add_insteon_fan_entities(discovery_info=None):
        """Add the Insteon entities for the platform."""
        async_add_insteon_entities(
            hass, Platform.FAN, InsteonFanEntity, async_add_entities, discovery_info
        )

    signal = f"{SIGNAL_ADD_ENTITIES}_{Platform.FAN}"
    async_dispatcher_connect(hass, signal, async_add_insteon_fan_entities)
    async_add_insteon_devices(
        hass,
        Platform.FAN,
        InsteonFanEntity,
        async_add_entities,
    )


class InsteonFanEntity(InsteonEntity, FanEntity):
    """An INSTEON fan entity."""

    _attr_supported_features = FanEntityFeature.SET_SPEED
    _attr_speed_count = 3

    @property
    def percentage(self) -> int | None:
        """Return the current speed percentage."""
        if self._insteon_device_group.value is None:
            return None
        return ranged_value_to_percentage(SPEED_RANGE, self._insteon_device_group.value)

    async def async_turn_on(
        self,
        percentage: int | None = None,
        preset_mode: str | None = None,
        **kwargs: Any,
    ) -> None:
        """Turn on the fan."""
        await self.async_set_percentage(percentage or 67)

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn off the fan."""
        await self._insteon_device.async_fan_off()

    async def async_set_percentage(self, percentage: int) -> None:
        """Set the speed percentage of the fan."""
        if percentage == 0:
            await self.async_turn_off()
            return
        on_level = math.ceil(percentage_to_ranged_value(SPEED_RANGE, percentage))
        await self._insteon_device.async_on(group=2, on_level=on_level)
