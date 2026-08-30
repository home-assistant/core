"""Number platform for Besen."""

from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import override

from besen.const import FALLBACK_MAX_CHARGE_AMPS, MIN_CHARGE_AMPS
from besen.models import BesenData

from homeassistant.components.number import (
    NumberDeviceClass,
    NumberEntity,
    NumberEntityDescription,
    NumberMode,
)
from homeassistant.const import PERCENTAGE, EntityCategory, UnitOfElectricCurrent
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import BesenConfigEntry
from .coordinator import BesenCoordinator
from .entity import BesenEntity

PARALLEL_UPDATES = 0


@dataclass(frozen=True, kw_only=True)
class BesenNumberEntityDescription(NumberEntityDescription):
    """Describe a Besen number entity."""

    value_fn: Callable[[BesenData], float | None]
    set_fn: Callable[[BesenCoordinator, float], Awaitable[None]]
    max_fn: Callable[[BesenData], float]


NUMBER_DESCRIPTIONS: tuple[BesenNumberEntityDescription, ...] = (
    BesenNumberEntityDescription(
        key="charging_current",
        translation_key="charging_current",
        device_class=NumberDeviceClass.CURRENT,
        entity_category=EntityCategory.CONFIG,
        mode=NumberMode.BOX,
        native_min_value=MIN_CHARGE_AMPS,
        native_step=1,
        native_unit_of_measurement=UnitOfElectricCurrent.AMPERE,
        value_fn=lambda data: data.config.charge_amps,
        set_fn=lambda coordinator, value: coordinator.async_set_charge_amps(int(value)),
        max_fn=lambda data: data.info.output_max_amps or FALLBACK_MAX_CHARGE_AMPS,
    ),
    BesenNumberEntityDescription(
        key="lcd_brightness",
        translation_key="lcd_brightness",
        entity_category=EntityCategory.CONFIG,
        entity_registry_enabled_default=False,
        mode=NumberMode.SLIDER,
        native_min_value=1,
        native_step=1,
        native_unit_of_measurement=PERCENTAGE,
        value_fn=lambda data: data.config.lcd_brightness,
        set_fn=lambda coordinator, value: coordinator.async_set_lcd_brightness(
            int(value)
        ),
        max_fn=lambda data: 100,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: BesenConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the Besen number platform."""

    async_add_entities(
        BesenNumber(entry.runtime_data, description)
        for description in NUMBER_DESCRIPTIONS
    )


class BesenNumber(BesenEntity, NumberEntity):
    """Representation of a Besen number."""

    entity_description: BesenNumberEntityDescription

    def __init__(
        self,
        coordinator: BesenCoordinator,
        description: BesenNumberEntityDescription,
    ) -> None:
        """Initialize a Besen number."""

        super().__init__(coordinator, description.key)
        self.entity_description = description

    @property
    @override
    def native_max_value(self) -> float:
        """Return the maximum value."""

        return self.entity_description.max_fn(self.coordinator.data)

    @property
    @override
    def native_value(self) -> float | None:
        """Return the configured value."""

        return self.entity_description.value_fn(self.coordinator.data)

    @override
    async def async_set_native_value(self, value: float) -> None:
        """Set the value."""

        await self.entity_description.set_fn(self.coordinator, value)
