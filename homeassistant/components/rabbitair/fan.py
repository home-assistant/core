"""Support for Rabbit Air fan entity."""
from __future__ import annotations

import logging
from typing import Any

from rabbitair import Mode, Model, Speed

from homeassistant.components.fan import (
    SUPPORT_PRESET_MODE,
    SUPPORT_SET_SPEED,
    FanEntity,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.util.percentage import (
    ordered_list_item_to_percentage,
    percentage_to_ordered_list_item,
)

from .const import DOMAIN, KEY_COORDINATOR, KEY_DEVICE
from .entity import RabbitAirBaseEntity

_LOGGER = logging.getLogger(__name__)

SPEED_LIST = [
    Speed.Silent,
    Speed.Low,
    Speed.Medium,
    Speed.High,
    Speed.Turbo,
]

PRESET_MODE_AUTO = "Auto"
PRESET_MODE_MANUAL = "Manual"
PRESET_MODE_POLLEN = "Pollen"

PRESET_MODES = {
    PRESET_MODE_AUTO: Mode.Auto,
    PRESET_MODE_MANUAL: Mode.Manual,
    PRESET_MODE_POLLEN: Mode.Pollen,
}


class RabbitAirFanEntity(RabbitAirBaseEntity, FanEntity):
    """Fan control functions of the Rabbit Air air purifier."""
    
    _attr_supported_features = SUPPORT_PRESET_MODE | SUPPORT_SET_SPEED


    async def async_set_preset_mode(self, preset_mode: str) -> None:
        """Set new preset mode."""
        await self._set_state(mode=PRESET_MODES[preset_mode])

    async def async_set_percentage(self, percentage: int) -> None:
        """Set the speed of the fan, as a percentage."""
        value = percentage_to_ordered_list_item(SPEED_LIST, percentage)
        await self._set_state(speed=value)

    async def async_turn_on(
        self,
        speed: str | None = None,
        percentage: int | None = None,
        preset_mode: str | None = None,
        **kwargs: Any,
    ) -> None:
        """Turn on the fan."""
        mode_value: Mode | None = None
        if preset_mode is not None:
            mode_value = PRESET_MODES[preset_mode]
        speed_value: Speed | None = None
        if percentage is not None:
            speed_value = percentage_to_ordered_list_item(SPEED_LIST, percentage)
        await self._set_state(power=True, mode=mode_value, speed=speed_value)

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the fan off."""
        await self._set_state(power=False)

    @property
    def is_on(self) -> bool | None:
        """Return true if device is on."""
        return self.coordinator.data.power

    @property
    def percentage(self) -> int | None:
        """Return the current speed as a percentage."""
        speed = self.coordinator.data.speed
        return (
            None
            if speed is None
            else 0
            if speed is Speed.SuperSilent
            else ordered_list_item_to_percentage(SPEED_LIST, speed)
        )

    @property
    def speed_count(self) -> int:
        """Return the number of speeds the fan supports."""
        return len(SPEED_LIST)

    @property
    def preset_mode(self) -> str | None:
        """Return the current preset mode."""
        mode = self.coordinator.data.mode
        if mode is None:
            return None
        # Get key by value in dictionary
        return next(k for k, v in PRESET_MODES.items() if v == mode)

    @property
    def preset_modes(self) -> list[str] | None:
        """Return a list of available preset modes."""
        if self._is_model(Model.MinusA2):
            return list(PRESET_MODES.keys())
        if self._is_model(Model.A3):
            # A3 does not support Pollen mode
            return [k for k in PRESET_MODES if k != PRESET_MODE_POLLEN]
        return None


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up a config entry."""
    coordinator = hass.data[DOMAIN][entry.entry_id][KEY_COORDINATOR]
    device = hass.data[DOMAIN][entry.entry_id][KEY_DEVICE]

    async_add_entities([RabbitAirFanEntity(coordinator, device, entry)])
