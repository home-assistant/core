"""Select platform for Indevolt integration."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Final

from homeassistant.components.select import SelectEntity, SelectEntityDescription
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import IndevoltConfigEntry
from .coordinator import IndevoltCoordinator
from .entity import IndevoltEntity

PARALLEL_UPDATES = 0


@dataclass(frozen=True, kw_only=True)
class IndevoltSelectEntityDescription(SelectEntityDescription):
    """Custom entity description class for Indevolt select entities."""

    read_key: str
    write_key: str
    value_to_option: dict[int, str]
    unavailable_values: list[int] = field(default_factory=list)
    generation: list[int] = field(default_factory=lambda: [1, 2])


SELECTS: Final = (
    IndevoltSelectEntityDescription(
        key="energy_mode",
        translation_key="energy_mode",
        read_key="7101",
        write_key="47005",
        value_to_option={
            1: "self_consumed_prioritized",
            4: "real_time_control",
            5: "charge_discharge_schedule",
        },
        unavailable_values=[0],
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: IndevoltConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the select platform for Indevolt."""
    coordinator = entry.runtime_data
    device_gen = coordinator.generation

    # Select initialization
    async_add_entities(
        IndevoltSelectEntity(coordinator=coordinator, description=description)
        for description in SELECTS
        if device_gen in description.generation
    )


class IndevoltSelectEntity(IndevoltEntity, SelectEntity):
    """Represents a select entity for Indevolt devices."""

    entity_description: IndevoltSelectEntityDescription

    def __init__(
        self,
        coordinator: IndevoltCoordinator,
        description: IndevoltSelectEntityDescription,
    ) -> None:
        """Initialize the Indevolt select entity."""
        super().__init__(coordinator)

        self.entity_description = description
        self._attr_unique_id = f"{self.serial_number}_{description.key}"
        self._attr_options = list(description.value_to_option.values())
        self._option_to_value = {v: k for k, v in description.value_to_option.items()}

    @property
    def current_option(self) -> str | None:
        """Return the currently selected option."""
        raw_value = self.coordinator.data.get(self.entity_description.read_key)
        if raw_value is None:
            return None

        return self.entity_description.value_to_option.get(raw_value)

    @property
    def available(self) -> bool:
        """Return False when the device is in a mode that cannot be selected."""
        if not super().available:
            return False

        raw_value = self.coordinator.data.get(self.entity_description.read_key)
        return raw_value not in self.entity_description.unavailable_values

    async def async_select_option(self, option: str) -> None:
        """Select a new option."""
        value = self._option_to_value[option]
        success = await self.coordinator.async_push_data(
            self.entity_description.write_key, value
        )

        if success:
            await self.coordinator.async_request_refresh()

        else:
            raise HomeAssistantError(f"Failed to set option {option} for {self.name}")
