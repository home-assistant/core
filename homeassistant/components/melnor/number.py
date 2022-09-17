"""Switch support for Melnor Bluetooth water timer."""

from __future__ import annotations

from collections.abc import Callable, Coroutine
from dataclasses import dataclass
from typing import Any

from melnor_bluetooth.device import Valve

from homeassistant.components.number import NumberEntity, NumberEntityDescription
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from .models import MelnorDataUpdateCoordinator, MelnorZoneEntity


@dataclass
class MelnorZoneNumberEntityDescriptionMixin:
    """Mixin for required keys."""

    set_num_fn: Callable[[Valve, int], Coroutine[Any, Any, None]]
    state_fn: Callable[[Valve], Any]


@dataclass
class MelnorZoneNumberEntityDescription(
    NumberEntityDescription, MelnorZoneNumberEntityDescriptionMixin
):
    """Describes Melnor switch entity."""


numbers = [
    MelnorZoneNumberEntityDescription(
        # native_unit_of_measurement="minutes",
        entity_category=EntityCategory.CONFIG,
        native_max_value=360,
        native_min_value=1,
        icon="mdi:timer-cog-outline",
        key="manual_minutes",
        name="Manual Minutes",
        set_num_fn=lambda valve, value: valve.set_manual_watering_minutes(value),
        state_fn=lambda valve: valve.manual_watering_minutes,
    )
]


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_devices: AddEntitiesCallback,
) -> None:
    """Set up the switch platform."""
    entities: list[MelnorZoneNumber] = []

    coordinator: MelnorDataUpdateCoordinator = hass.data[DOMAIN][config_entry.entry_id]

    # This device may not have 4 valves total, but the library will only expose the right number of valves
    for i in range(1, 5):
        valve = coordinator.data[f"zone{i}"]

        if valve is not None:

            for description in numbers:
                entities.append(MelnorZoneNumber(coordinator, valve, description))

    async_add_devices(entities)


class MelnorZoneNumber(MelnorZoneEntity, NumberEntity):
    """A switch implementation for a melnor device."""

    entity_description: MelnorZoneNumberEntityDescription

    def __init__(
        self,
        coordinator: MelnorDataUpdateCoordinator,
        valve: Valve,
        entity_description: MelnorZoneNumberEntityDescription,
    ) -> None:
        """Initialize a switch for a melnor device."""
        super().__init__(coordinator, valve)

        self._attr_unique_id = (
            f"{self._device.mac}-zone{valve.id}-{entity_description.key}"
        )
        self.entity_description = entity_description

    @property
    def native_value(self) -> float | None:
        """Return true if device is on."""
        return self._valve.manual_watering_minutes

    async def async_set_native_value(self, value: float) -> None:
        """Update the current value."""
        await self.entity_description.set_num_fn(self._valve, int(value))
        self._async_write_ha_state()
