"""Number platform for Indevolt integration."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Final

from homeassistant.components.number import (
    NumberEntity,
    NumberEntityDescription,
    NumberMode,
)
from homeassistant.const import PERCENTAGE, UnitOfPower
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import IndevoltConfigEntry
from .coordinator import IndevoltCoordinator
from .entity import IndevoltEntity

PARALLEL_UPDATES = 0


@dataclass(frozen=True, kw_only=True)
class IndevoltNumberEntityDescription(NumberEntityDescription):
    """Custom entity description class for Indevolt number entities."""

    generation: list[int] = field(default_factory=lambda: [1, 2])
    read_key: str
    write_key: str


NUMBERS: Final = (
    IndevoltNumberEntityDescription(
        key="discharge_limit",
        generation=[2],
        translation_key="discharge_limit",
        read_key="6105",
        write_key="1142",
        native_min_value=0,
        native_max_value=100,
        native_step=1,
        native_unit_of_measurement=PERCENTAGE,
    ),
    IndevoltNumberEntityDescription(
        key="max_ac_output_power",
        generation=[2],
        translation_key="max_ac_output_power",
        read_key="11011",
        write_key="1147",
        native_min_value=0,
        native_max_value=2400,
        native_step=100,
        native_unit_of_measurement=UnitOfPower.WATT,
    ),
    IndevoltNumberEntityDescription(
        key="inverter_input_limit",
        generation=[2],
        translation_key="inverter_input_limit",
        read_key="11009",
        write_key="1138",
        native_min_value=100,
        native_max_value=2400,
        native_step=100,
        native_unit_of_measurement=UnitOfPower.WATT,
    ),
    IndevoltNumberEntityDescription(
        key="feedin_power_limit",
        generation=[2],
        translation_key="feedin_power_limit",
        read_key="11010",
        write_key="1146",
        native_min_value=0,
        native_max_value=2400,
        native_step=100,
        native_unit_of_measurement=UnitOfPower.WATT,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: IndevoltConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the number platform for Indevolt."""
    coordinator = entry.runtime_data
    device_gen = coordinator.generation

    # Number initialization
    async_add_entities(
        IndevoltNumberEntity(coordinator, description)
        for description in NUMBERS
        if device_gen in description.generation
    )


class IndevoltNumberEntity(IndevoltEntity, NumberEntity):
    """Represents a number entity for Indevolt devices."""

    entity_description: IndevoltNumberEntityDescription
    _attr_mode = NumberMode.BOX

    def __init__(
        self,
        coordinator: IndevoltCoordinator,
        description: IndevoltNumberEntityDescription,
    ) -> None:
        """Initialize the Indevolt number entity."""
        super().__init__(coordinator)

        self.entity_description = description
        self._attr_unique_id = f"{self.serial_number}_{description.key}"

    @property
    def native_value(self) -> float | None:
        """Return the current value of the entity."""
        raw_value = self.coordinator.data.get(self.entity_description.read_key)
        if raw_value is None:
            return None

        try:
            return float(raw_value)
        except TypeError, ValueError:
            return None

    async def async_set_native_value(self, value: float) -> None:
        """Set a new value for the entity."""

        int_value = int(value)
        success = await self.coordinator.async_push_data(
            self.entity_description.write_key, int_value
        )

        if success:
            new_data = dict(self.coordinator.data)
            new_data[self.entity_description.read_key] = int_value
            self.coordinator.async_set_updated_data(new_data)
