"""Support for LED numbers."""
from __future__ import annotations

from typing import cast

from homeassistant import config_entries
from homeassistant.components.number import NumberEntity
from homeassistant.components.number.const import MODE_SLIDER
from homeassistant.const import CONF_NAME
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import FluxLedUpdateCoordinator
from .const import DOMAIN, EFFECT_SUPPORT_MODES
from .entity import FluxEntity
from .util import _hass_color_modes


async def async_setup_entry(
    hass: HomeAssistant,
    entry: config_entries.ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the Flux lights."""
    coordinator: FluxLedUpdateCoordinator = hass.data[DOMAIN][entry.entry_id]

    color_modes = _hass_color_modes(coordinator.device)
    if not color_modes.intersection(EFFECT_SUPPORT_MODES):
        return

    async_add_entities(
        [
            FluxNumber(
                coordinator,
                entry.unique_id,
                entry.data[CONF_NAME],
            )
        ]
    )


class FluxNumber(FluxEntity, CoordinatorEntity, NumberEntity):
    """Defines a flux_led speed number."""

    _attr_min_value = 1
    _attr_max_value = 100
    _attr_step = 1
    _attr_mode = MODE_SLIDER
    _attr_icon = "mdi:speedometer"

    def __init__(
        self,
        coordinator: FluxLedUpdateCoordinator,
        unique_id: str | None,
        name: str,
    ) -> None:
        """Initialize the flux number."""
        super().__init__(coordinator, unique_id, name)
        self._attr_name = f"{name} Effect Speed"

    @property
    def value(self) -> float:
        """Return the effect speed."""
        return cast(float, self._device.speed)

    async def async_set_value(self, value: float) -> None:
        """Set the flux speed value."""
        current_effect = self._device.effect
        new_speed = int(value)
        if not current_effect:
            raise HomeAssistantError(
                "Speed can only be adjusted when an effect is active"
            )
        if self._device.original_addressable and not self._device.is_on:
            raise HomeAssistantError("Speed can only be adjusted when the light is on")
        await self._device.async_set_effect(current_effect, new_speed)
        await self.coordinator.async_request_refresh()
