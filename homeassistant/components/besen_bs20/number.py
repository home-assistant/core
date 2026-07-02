"""Number platform for Besen BS20."""

from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import override

from besen_bs20.models import BesenBS20Data

from homeassistant.components.number import (
    NumberEntity,
    NumberEntityDescription,
    NumberMode,
)
from homeassistant.const import PERCENTAGE, EntityCategory, UnitOfElectricCurrent
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import BesenBS20ConfigEntry
from .const import FALLBACK_MAX_CHARGE_AMPS, MIN_CHARGE_AMPS
from .coordinator import BesenBS20Coordinator
from .entity import BesenBS20Entity

PARALLEL_UPDATES = 0


@dataclass(frozen=True, kw_only=True)
class BesenNumberEntityDescription(NumberEntityDescription):
    """Besen number description."""

    value_fn: Callable[[BesenBS20Data], float | None]
    set_fn: Callable[[BesenBS20Coordinator, float], Awaitable[None]]
    max_fn: Callable[[BesenBS20Data], float]


NUMBERS: tuple[BesenNumberEntityDescription, ...] = (
    BesenNumberEntityDescription(
        key="charge_amps",
        name="Charge Amps",
        value_fn=lambda data: data.config.charge_amps,
        set_fn=lambda coordinator, value: coordinator.async_set_charge_amps(int(value)),
        max_fn=lambda data: data.info.output_max_amps or FALLBACK_MAX_CHARGE_AMPS,
        native_min_value=MIN_CHARGE_AMPS,
        native_step=1,
        native_unit_of_measurement=UnitOfElectricCurrent.AMPERE,
        mode=NumberMode.BOX,
    ),
    BesenNumberEntityDescription(
        key="lcd_brightness",
        name="LCD Brightness",
        value_fn=lambda data: data.config.lcd_brightness,
        set_fn=lambda coordinator, value: coordinator.async_set_lcd_brightness(
            int(value)
        ),
        max_fn=lambda data: 100,
        native_min_value=1,
        native_step=1,
        native_unit_of_measurement=PERCENTAGE,
        mode=NumberMode.SLIDER,
        entity_category=EntityCategory.CONFIG,
        entity_registry_enabled_default=False,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: BesenBS20ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Besen BS20 numbers."""

    async_add_entities(
        [
            BesenBS20Number(entry.runtime_data.coordinator, description)
            for description in NUMBERS
        ]
    )


class BesenBS20Number(BesenBS20Entity, NumberEntity):
    """Besen BS20 number entity."""

    entity_description: BesenNumberEntityDescription

    def __init__(
        self,
        coordinator: BesenBS20Coordinator,
        description: BesenNumberEntityDescription,
    ) -> None:
        """Initialize the number."""

        super().__init__(coordinator, description.key)
        self.entity_description = description

    @property
    @override
    def native_value(self) -> float | None:
        """Return the number value."""

        data = self.coordinator.data or self.coordinator.client.state
        return self.entity_description.value_fn(data)

    @property
    @override
    def native_max_value(self) -> float:
        """Return dynamic max value."""

        data = self.coordinator.data or self.coordinator.client.state
        return self.entity_description.max_fn(data)

    @override
    async def async_set_native_value(self, value: float) -> None:
        """Set a number value."""

        await self.entity_description.set_fn(self.coordinator, value)
