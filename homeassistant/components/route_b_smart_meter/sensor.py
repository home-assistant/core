"""Smart Meter B Route."""

from collections.abc import Callable
from dataclasses import dataclass

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import UnitOfElectricCurrent, UnitOfEnergy, UnitOfPower
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.typing import StateType
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import BRouteConfigEntry
from .const import (
    ATTR_API_INSTANTANEOUS_CURRENT_R_PHASE,
    ATTR_API_INSTANTANEOUS_CURRENT_T_PHASE,
    ATTR_API_INSTANTANEOUS_POWER,
    ATTR_API_TOTAL_CONSUMPTION,
    DOMAIN,
)
from .coordinator import BRouteData, BRouteUpdateCoordinator


@dataclass(frozen=True, kw_only=True)
class SensorEntityDescriptionWithValueAccessor(SensorEntityDescription):
    """Sensor entity description with data accessor."""

    value_accessor: Callable[[BRouteData], StateType]


SENSOR_DESCRIPTIONS = (
    SensorEntityDescriptionWithValueAccessor(
        key=ATTR_API_INSTANTANEOUS_CURRENT_R_PHASE,
        translation_key=ATTR_API_INSTANTANEOUS_CURRENT_R_PHASE,
        device_class=SensorDeviceClass.CURRENT,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfElectricCurrent.AMPERE,
        value_accessor=lambda data: data.instantaneous_current_r_phase,
    ),
    SensorEntityDescriptionWithValueAccessor(
        key=ATTR_API_INSTANTANEOUS_CURRENT_T_PHASE,
        translation_key=ATTR_API_INSTANTANEOUS_CURRENT_T_PHASE,
        device_class=SensorDeviceClass.CURRENT,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfElectricCurrent.AMPERE,
        value_accessor=lambda data: data.instantaneous_current_t_phase,
    ),
    SensorEntityDescriptionWithValueAccessor(
        key=ATTR_API_INSTANTANEOUS_POWER,
        translation_key=ATTR_API_INSTANTANEOUS_POWER,
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfPower.WATT,
        value_accessor=lambda data: data.instantaneous_power,
    ),
    SensorEntityDescriptionWithValueAccessor(
        key=ATTR_API_TOTAL_CONSUMPTION,
        translation_key=ATTR_API_TOTAL_CONSUMPTION,
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL,
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        value_accessor=lambda data: data.total_consumption,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: BRouteConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Smart Meter B-route entry."""
    coordinator = entry.runtime_data

    async_add_entities(
        SmartMeterBRouteSensor(coordinator, description)
        for description in SENSOR_DESCRIPTIONS
    )


class SmartMeterBRouteSensor(CoordinatorEntity[BRouteUpdateCoordinator], SensorEntity):
    """Representation of a Smart Meter B-route sensor entity."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: BRouteUpdateCoordinator,
        description: SensorEntityDescriptionWithValueAccessor,
    ) -> None:
        """Initialize Smart Meter B-route sensor entity."""
        super().__init__(coordinator)
        self.entity_description: SensorEntityDescriptionWithValueAccessor = description
        self._attr_unique_id = f"{coordinator.bid}_{description.key}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, coordinator.bid)},
            name=f"Route B Smart Meter {coordinator.bid}",
        )

    @property
    def native_value(self) -> StateType:
        """Return the state of the sensor."""
        return self.entity_description.value_accessor(self.coordinator.data)
