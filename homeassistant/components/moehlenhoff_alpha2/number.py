"""Number platform for the Möhlenhoff Alpha2."""

from dataclasses import dataclass
from typing import override

from homeassistant.components.number import (
    NumberDeviceClass,
    NumberEntity,
    NumberEntityDescription,
    NumberMode,
)
from homeassistant.const import EntityCategory, UnitOfTemperature
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .coordinator import Alpha2BaseCoordinator, Alpha2ConfigEntry
from .entity import Alpha2RoomEntity


@dataclass(frozen=True, kw_only=True)
class Alpha2NumberEntityDescription(NumberEntityDescription):
    """Describe an Alpha2 number entity."""

    attribute: str


NUMBER_DESCRIPTIONS: tuple[Alpha2NumberEntityDescription, ...] = (
    Alpha2NumberEntityDescription(
        key="temperature_offset",
        translation_key="temperature_offset",
        name="Temperature offset",
        attribute="OFFSET",
        device_class=NumberDeviceClass.TEMPERATURE,
        entity_category=EntityCategory.CONFIG,
        native_min_value=-5,
        native_max_value=5,
        native_step=0.1,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        mode=NumberMode.BOX,
    ),
    Alpha2NumberEntityDescription(
        key="heating_temperature_day",
        translation_key="heating_temperature_day",
        name="Heating temperature (day)",
        attribute="T_HEAT_DAY",
        device_class=NumberDeviceClass.TEMPERATURE,
        entity_category=EntityCategory.CONFIG,
        native_min_value=0,
        native_max_value=50,
        native_step=0.1,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        mode=NumberMode.BOX,
    ),
    Alpha2NumberEntityDescription(
        key="heating_temperature_night",
        translation_key="heating_temperature_night",
        name="Heating temperature (night)",
        attribute="T_HEAT_NIGHT",
        device_class=NumberDeviceClass.TEMPERATURE,
        entity_category=EntityCategory.CONFIG,
        native_min_value=0,
        native_max_value=50,
        native_step=0.1,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        mode=NumberMode.BOX,
    ),
    Alpha2NumberEntityDescription(
        key="cooling_temperature_day",
        translation_key="cooling_temperature_day",
        name="Cooling temperature (day)",
        attribute="T_COOL_DAY",
        device_class=NumberDeviceClass.TEMPERATURE,
        entity_category=EntityCategory.CONFIG,
        native_min_value=0,
        native_max_value=50,
        native_step=0.1,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        mode=NumberMode.BOX,
    ),
    Alpha2NumberEntityDescription(
        key="cooling_temperature_night",
        translation_key="cooling_temperature_night",
        name="Cooling temperature (night)",
        attribute="T_COOL_NIGHT",
        device_class=NumberDeviceClass.TEMPERATURE,
        entity_category=EntityCategory.CONFIG,
        native_min_value=0,
        native_max_value=50,
        native_step=0.1,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        mode=NumberMode.BOX,
    ),
    Alpha2NumberEntityDescription(
        key="minimum_target_temperature",
        translation_key="minimum_target_temperature",
        name="Minimum target temperature",
        attribute="T_TARGET_MIN",
        device_class=NumberDeviceClass.TEMPERATURE,
        entity_category=EntityCategory.CONFIG,
        native_min_value=0,
        native_max_value=50,
        native_step=0.1,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        mode=NumberMode.BOX,
    ),
    Alpha2NumberEntityDescription(
        key="maximum_target_temperature",
        translation_key="maximum_target_temperature",
        name="Maximum target temperature",
        attribute="T_TARGET_MAX",
        device_class=NumberDeviceClass.TEMPERATURE,
        entity_category=EntityCategory.CONFIG,
        native_min_value=0,
        native_max_value=50,
        native_step=0.1,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        mode=NumberMode.BOX,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: Alpha2ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Alpha2 number entities."""
    coordinator = entry.runtime_data
    async_add_entities(
        Alpha2Number(coordinator, heat_area_id, description)
        for heat_area_id, heat_area in coordinator.data["heat_areas"].items()
        for description in NUMBER_DESCRIPTIONS
        if description.attribute in heat_area
    )


class Alpha2Number(Alpha2RoomEntity, NumberEntity):
    """Represent a writable Alpha2 room setting."""

    entity_description: Alpha2NumberEntityDescription

    def __init__(
        self,
        coordinator: Alpha2BaseCoordinator,
        heat_area_id: str,
        description: Alpha2NumberEntityDescription,
    ) -> None:
        """Initialize the number entity."""
        super().__init__(coordinator, heat_area_id)
        self.entity_description = description
        self._attr_unique_id = f"{heat_area_id}:{description.key}"

    @property
    @override
    def native_value(self) -> float | None:
        """Return the current room setting."""
        value = self.coordinator.data["heat_areas"][self.heat_area_id].get(
            self.entity_description.attribute
        )
        return None if value is None else float(value)

    @override
    async def async_set_native_value(self, value: float) -> None:
        """Set the room setting."""
        await self.coordinator.async_set_heat_area_attributes(
            self.heat_area_id, {self.entity_description.attribute: value}
        )
