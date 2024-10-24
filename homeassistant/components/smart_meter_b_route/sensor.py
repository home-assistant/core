"""Smart Meter B Route."""

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import UnitOfElectricCurrent, UnitOfEnergy, UnitOfPower
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import StateType
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import (
    ATTR_API_INSTANTANEOUS_CURRENT_R_PHASE,
    ATTR_API_INSTANTANEOUS_CURRENT_T_PHASE,
    ATTR_API_INSTANTANEOUS_POWER,
    ATTR_API_TOTAL_CONSUMPTION,
    DOMAIN,
)
from .coordinator import BRouteUpdateCoordinator

SENSOR_DESCRIPTIONS = (
    SensorEntityDescription(
        key=ATTR_API_INSTANTANEOUS_CURRENT_R_PHASE,
        translation_key=ATTR_API_INSTANTANEOUS_CURRENT_R_PHASE,
        device_class=SensorDeviceClass.CURRENT,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfElectricCurrent.AMPERE,
    ),
    SensorEntityDescription(
        key=ATTR_API_INSTANTANEOUS_CURRENT_T_PHASE,
        translation_key=ATTR_API_INSTANTANEOUS_CURRENT_T_PHASE,
        device_class=SensorDeviceClass.CURRENT,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfElectricCurrent.AMPERE,
    ),
    SensorEntityDescription(
        key=ATTR_API_INSTANTANEOUS_POWER,
        translation_key=ATTR_API_INSTANTANEOUS_POWER,
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfPower.WATT,
    ),
    SensorEntityDescription(
        key=ATTR_API_TOTAL_CONSUMPTION,
        translation_key=ATTR_API_TOTAL_CONSUMPTION,
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL,
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
    ),
)


async def async_setup_entry(
    _: HomeAssistant,
    config: ConfigEntry[BRouteUpdateCoordinator],
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Smart Meter B-route entry."""
    coordinator = config.runtime_data

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
        description: SensorEntityDescription,
    ) -> None:
        """Initialize Smart Meter B-route sensor entity."""
        super().__init__(coordinator)
        self.entity_description = description
        self._attr_unique_id = f"{coordinator.bid}_{description.key}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, coordinator.bid)},
            name=f"Smart Meter B Route {coordinator.bid}",
        )

    @property
    def native_value(self) -> StateType:
        """Return the state of the sensor."""
        return self.coordinator.data.get(self.entity_description.key)
