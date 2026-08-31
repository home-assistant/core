"""Support for Homevolt number entities."""

from typing import override

from homeassistant.components.number import NumberEntity, NumberEntityDescription
from homeassistant.const import PERCENTAGE, EntityCategory, UnitOfPower
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .coordinator import HomevoltConfigEntry, HomevoltDataUpdateCoordinator
from .entity import HomevoltEntity, homevolt_exception_handler

PARALLEL_UPDATES = 0  # Coordinator-based updates


NUMBER_DESCRIPTIONS: tuple[NumberEntityDescription, ...] = (
    NumberEntityDescription(
        key="setpoint",
        translation_key="setpoint",
        native_min_value=0,
        native_max_value=20000,
        native_step=100,
        native_unit_of_measurement=UnitOfPower.WATT,
        entity_category=EntityCategory.CONFIG,
    ),
    NumberEntityDescription(
        key="max_charge",
        translation_key="max_charge",
        native_min_value=0,
        native_max_value=20000,
        native_step=100,
        native_unit_of_measurement=UnitOfPower.WATT,
        entity_category=EntityCategory.CONFIG,
    ),
    NumberEntityDescription(
        key="max_discharge",
        translation_key="max_discharge",
        native_min_value=0,
        native_max_value=20000,
        native_step=100,
        native_unit_of_measurement=UnitOfPower.WATT,
        entity_category=EntityCategory.CONFIG,
    ),
    NumberEntityDescription(
        key="min_soc",
        translation_key="min_soc",
        native_min_value=0,
        native_max_value=100,
        native_step=1,
        native_unit_of_measurement=PERCENTAGE,
        entity_category=EntityCategory.CONFIG,
    ),
    NumberEntityDescription(
        key="max_soc",
        translation_key="max_soc",
        native_min_value=0,
        native_max_value=100,
        native_step=1,
        native_unit_of_measurement=PERCENTAGE,
        entity_category=EntityCategory.CONFIG,
    ),
    NumberEntityDescription(
        key="grid_import_limit",
        translation_key="grid_import_limit",
        native_min_value=0,
        native_max_value=20000,
        native_step=100,
        native_unit_of_measurement=UnitOfPower.WATT,
        entity_category=EntityCategory.CONFIG,
    ),
    NumberEntityDescription(
        key="grid_export_limit",
        translation_key="grid_export_limit",
        native_min_value=0,
        native_max_value=20000,
        native_step=100,
        native_unit_of_measurement=UnitOfPower.WATT,
        entity_category=EntityCategory.CONFIG,
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
        [
            HomevoltNumberEntity(coordinator, description)
            for description in NUMBER_DESCRIPTIONS
        ]
    )


class HomevoltNumberEntity(HomevoltEntity, NumberEntity):
    """Representation of a Homevolt number entity."""

    entity_description: NumberEntityDescription
    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: HomevoltDataUpdateCoordinator,
        description: NumberEntityDescription,
    ) -> None:
        """Initialize the number entity."""
        self.entity_description = description
        self._attr_unique_id = f"{coordinator.data.unique_id}_{description.key}"
        device_id = coordinator.data.unique_id
        super().__init__(coordinator, f"ems_{device_id}")

    @property
    @override
    def available(self) -> bool:
        """Return whether the current manual schedule supports parameter writes."""
        return super().available and self.coordinator.client.battery_parameters_writable

    @property
    @override
    def native_value(self) -> float | None:
        """Return the current value."""
        value = self.coordinator.client.schedule.get(self.entity_description.key)
        return float(value) if value is not None else None

    @homevolt_exception_handler
    @override
    async def async_set_native_value(self, value: float) -> None:
        """Set the value."""
        key = self.entity_description.key
        await self.coordinator.client.set_battery_parameters(**{key: int(value)})
        await self.coordinator.async_request_refresh()
