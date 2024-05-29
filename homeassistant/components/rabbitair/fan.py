"""Support for Rabbit Air fan entity."""

from __future__ import annotations

from typing import Any

from rabbitair import Mode, Model, Speed

from homeassistant.components.fan import FanEntity, FanEntityFeature
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.util.percentage import (
    ordered_list_item_to_percentage,
    percentage_to_ordered_list_item,
)

from .const import DOMAIN
from .coordinator import RabbitAirDataUpdateCoordinator
from .entity import RabbitAirBaseEntity

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


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up a config entry."""
    coordinator: RabbitAirDataUpdateCoordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities([RabbitAirFanEntity(coordinator, entry)])


class RabbitAirFanEntity(RabbitAirBaseEntity, FanEntity):
    """Fan control functions of the Rabbit Air air purifier."""

    _attr_supported_features = FanEntityFeature.PRESET_MODE | FanEntityFeature.SET_SPEED

    def __init__(
        self,
        coordinator: RabbitAirDataUpdateCoordinator,
        entry: ConfigEntry,
    ) -> None:
        """Initialize the entity."""
        super().__init__(coordinator, entry)

        if self._is_model(Model.MinusA2):
            self._attr_preset_modes = list(PRESET_MODES)
        elif self._is_model(Model.A3):
            # A3 does not support Pollen mode
            self._attr_preset_modes = [
                k for k in PRESET_MODES if k != PRESET_MODE_POLLEN
            ]

        self._attr_speed_count = len(SPEED_LIST)

        self._get_state_from_coordinator_data()

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        self._get_state_from_coordinator_data()
        super()._handle_coordinator_update()

    def _get_state_from_coordinator_data(self) -> None:
        """Populate the entity fields with values from the coordinator data."""
        data = self.coordinator.data

        # Speed as a percentage
        if not data.power:
            self._attr_percentage = 0
        elif data.speed is None:
            self._attr_percentage = None
        elif data.speed is Speed.SuperSilent:
            self._attr_percentage = 1
        else:
            self._attr_percentage = ordered_list_item_to_percentage(
                SPEED_LIST, data.speed
            )

        # Preset mode
        if not data.power or data.mode is None:
            self._attr_preset_mode = None
        else:
            # Get key by value in dictionary
            self._attr_preset_mode = next(
                k for k, v in PRESET_MODES.items() if v == data.mode
            )

    async def async_set_preset_mode(self, preset_mode: str) -> None:
        """Set new preset mode."""
        await self._set_state(power=True, mode=PRESET_MODES[preset_mode])
        self._attr_preset_mode = preset_mode
        self.async_write_ha_state()

    async def async_set_percentage(self, percentage: int) -> None:
        """Set the speed of the fan, as a percentage."""
        if percentage > 0:
            value = percentage_to_ordered_list_item(SPEED_LIST, percentage)
            await self._set_state(power=True, speed=value)
            self._attr_percentage = percentage
        else:
            await self._set_state(power=False)
            self._attr_percentage = 0
            self._attr_preset_mode = None
        self.async_write_ha_state()

    async def async_turn_on(
        self,
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
        if percentage is not None:
            self._attr_percentage = percentage
        if preset_mode is not None:
            self._attr_preset_mode = preset_mode
        self.async_write_ha_state()

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the fan off."""
        await self._set_state(power=False)
        self._attr_percentage = 0
        self._attr_preset_mode = None
        self.async_write_ha_state()
