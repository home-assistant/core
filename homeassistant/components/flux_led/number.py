"""Support for LED numbers."""
from __future__ import annotations

from typing import cast

from homeassistant import config_entries
from homeassistant.components.number import NumberEntity
from homeassistant.const import CONF_NAME, ENTITY_CATEGORY_CONFIG
from homeassistant.core import HomeAssistant
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

    _attr_step = 1
    _attr_min_value = 1
    _attr_max_value = 100

    def __init__(
        self,
        coordinator: FluxLedUpdateCoordinator,
        unique_id: str | None,
        name: str,
    ) -> None:
        """Initialize the flux number."""
        super().__init__(coordinator, unique_id, f"{name} Effect Speed")
        self._attr_icon = "mdi:speedometer"
        self._attr_entity_category = ENTITY_CATEGORY_CONFIG

    @property
    def value(self) -> int | None:
        """Return the effect speed."""
        return cast(int, self._device.speed)

    async def async_set_value(self, value: float) -> None:
        """Set the flux speed value."""
        await self._device.async_set_effect(self._device.effect, value)
