"""Support for Homevolt number entities."""

from __future__ import annotations

from dataclasses import dataclass

from homeassistant.components.number import (
    NumberDeviceClass,
    NumberEntity,
    NumberEntityDescription,
)
from homeassistant.const import PERCENTAGE, EntityCategory, UnitOfPower
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .coordinator import HomevoltConfigEntry, HomevoltDataUpdateCoordinator
from .entity import HomevoltEntity, homevolt_exception_handler

PARALLEL_UPDATES = 0  # Coordinator-based updates


@dataclass(frozen=True, kw_only=True)
class HomevoltNumberEntityDescription(NumberEntityDescription):
    """Describes a Homevolt number entity."""

    available_modes: list[int] | None = None  # None means available in all modes

    def get_value(self, coordinator: HomevoltDataUpdateCoordinator) -> float | None:
        """Get the value from the coordinator based on the key."""
        return coordinator.client.schedule.get(self.key)


NUMBER_DESCRIPTIONS: tuple[HomevoltNumberEntityDescription, ...] = (
    HomevoltNumberEntityDescription(
        key="setpoint",
        translation_key="setpoint",
        device_class=NumberDeviceClass.POWER,
        entity_category=EntityCategory.CONFIG,
        native_unit_of_measurement=UnitOfPower.WATT,
        native_min_value=0,
        native_max_value=7000,
        native_step=1,
        available_modes=[1, 2, 7, 8],  # Inverter/solar charge/discharge modes
    ),
    HomevoltNumberEntityDescription(
        key="max_charge",
        translation_key="max_charge",
        device_class=NumberDeviceClass.POWER,
        entity_category=EntityCategory.CONFIG,
        native_unit_of_measurement=UnitOfPower.WATT,
        native_min_value=0,
        native_max_value=7000,
        native_step=1,
    ),
    HomevoltNumberEntityDescription(
        key="max_discharge",
        translation_key="max_discharge",
        device_class=NumberDeviceClass.POWER,
        entity_category=EntityCategory.CONFIG,
        native_unit_of_measurement=UnitOfPower.WATT,
        native_min_value=0,
        native_max_value=7000,
        native_step=1,
    ),
    HomevoltNumberEntityDescription(
        key="min_soc",
        translation_key="min_soc",
        device_class=NumberDeviceClass.BATTERY,
        entity_category=EntityCategory.CONFIG,
        native_unit_of_measurement=PERCENTAGE,
        native_min_value=0,
        native_max_value=100,
        native_step=1,
    ),
    HomevoltNumberEntityDescription(
        key="max_soc",
        translation_key="max_soc",
        device_class=NumberDeviceClass.BATTERY,
        entity_category=EntityCategory.CONFIG,
        native_unit_of_measurement=PERCENTAGE,
        native_min_value=0,
        native_max_value=100,
        native_step=1,
    ),
    HomevoltNumberEntityDescription(
        key="grid_import_limit",
        translation_key="grid_import_limit",
        device_class=NumberDeviceClass.POWER,
        entity_category=EntityCategory.CONFIG,
        native_unit_of_measurement=UnitOfPower.WATT,
        native_min_value=0,
        native_max_value=7000,
        native_step=1,
        available_modes=[3, 5],  # Grid charge modes
    ),
    HomevoltNumberEntityDescription(
        key="grid_export_limit",
        translation_key="grid_export_limit",
        device_class=NumberDeviceClass.POWER,
        entity_category=EntityCategory.CONFIG,
        native_unit_of_measurement=UnitOfPower.WATT,
        native_min_value=0,
        native_max_value=7000,
        native_step=1,
        available_modes=[4, 5],  # Grid discharge modes
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: HomevoltConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Homevolt number entities."""
    coordinator = entry.runtime_data
    async_add_entities(
        HomevoltNumber(coordinator, description) for description in NUMBER_DESCRIPTIONS
    )


class HomevoltNumber(HomevoltEntity, NumberEntity):
    """Representation of a Homevolt number entity."""

    entity_description: HomevoltNumberEntityDescription

    def __init__(
        self,
        coordinator: HomevoltDataUpdateCoordinator,
        description: HomevoltNumberEntityDescription,
    ) -> None:
        """Initialize the number entity."""
        self.entity_description = description
        self._attr_unique_id = f"{coordinator.data.unique_id}_{description.key}"
        device_id = coordinator.data.unique_id
        super().__init__(coordinator, f"ems_{device_id}")

    @property
    def available(self) -> bool:
        """Return if entity is available based on current mode."""
        if not super().available:
            return False

        if self.entity_description.available_modes is not None:
            current_mode = self.coordinator.client.schedule_mode
            if current_mode not in self.entity_description.available_modes:
                return False
        return True

    @property
    def native_value(self) -> float | None:
        """Return the current value."""
        return self.entity_description.get_value(self.coordinator)

    @homevolt_exception_handler
    async def async_set_native_value(self, value: float) -> None:
        """Set the value."""
        kwargs = {self.entity_description.key: int(value)}
        await self.coordinator.client.set_battery_mode(**kwargs)
        await self.coordinator.async_request_refresh()
