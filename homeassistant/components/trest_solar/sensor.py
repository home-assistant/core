"""Entity that represents the trest solar controller and its data values."""

from datetime import datetime

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
)
from homeassistant.const import UnitOfPower
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import StateType
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import TrestConfigEntry
from .const import DOMAIN
from .coordinator import TrestDataCoordinator

SENSOR_TYPES: tuple[SensorEntityDescription, ...] = (
    SensorEntityDescription(
        key="battery_discharge",
        translation_key="battery_discharge",
        device_class=SensorDeviceClass.POWER,
        native_unit_of_measurement=UnitOfPower.KILO_WATT,
    ),
    SensorEntityDescription(
        key="battery_charge",
        translation_key="battery_charge",
        device_class=SensorDeviceClass.POWER,
        native_unit_of_measurement=UnitOfPower.KILO_WATT,
    ),
    SensorEntityDescription(
        key="battery_capacity",
        translation_key="battery_capacity",
        device_class=SensorDeviceClass.BATTERY,
        native_unit_of_measurement=UnitOfPower.KILO_WATT,
    ),
    SensorEntityDescription(
        key="battery_stored_power",
        translation_key="battery_stored_power",
        device_class=SensorDeviceClass.ENERGY,
        native_unit_of_measurement=UnitOfPower.KILO_WATT,
    ),
    SensorEntityDescription(
        key="total_load_active_power",
        translation_key="total_load_active_power",
        device_class=SensorDeviceClass.POWER,
        native_unit_of_measurement=UnitOfPower.KILO_WATT,
    ),
    SensorEntityDescription(
        key="realtime_solar",
        translation_key="realtime_solar",
        device_class=SensorDeviceClass.POWER,
        native_unit_of_measurement=UnitOfPower.KILO_WATT,
    ),
    SensorEntityDescription(
        key="solar_profile",
        translation_key="solar_profile",
        device_class=SensorDeviceClass.POWER,
    ),
    SensorEntityDescription(
        key="daily_yeild",
        translation_key="daily_yeild",
        device_class=SensorDeviceClass.ENERGY,
        native_unit_of_measurement="kW",
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: TrestConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Add a Trest Solar Controller entry."""
    coordinator = entry.runtime_data

    async_add_entities(
        TrestSolarControllerSensor(coordinator, entry.entry_id, description)
        for description in SENSOR_TYPES
    )


class TrestSolarControllerSensor(CoordinatorEntity[TrestDataCoordinator], SensorEntity):
    """The sensor for Trest Solar Controller."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: TrestDataCoordinator,
        entry_id: str,
        description: SensorEntityDescription,
    ) -> None:
        """TrestSolarControllerSensor constructor."""
        super().__init__(coordinator)

        self.entity_description = description
        self._attr_unique_id = f"{entry_id}.{description.key}"
        self._attr_device_info = DeviceInfo(
            name="Trest Solar Controller",
            identifiers={(DOMAIN, entry_id)},
            entry_type=DeviceEntryType.SERVICE,
        )

    @property
    def native_value(self) -> StateType | datetime | None:
        """Return the state of the sensor."""

        key = self.entity_description.key
        return self.coordinator.data.to_dict().get(key)
