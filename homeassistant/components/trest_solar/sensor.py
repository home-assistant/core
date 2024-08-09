"""Entity that represents the trest solar controller and its data values."""

from datetime import datetime

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import TrestConfigEntry
from .const import DOMAIN
from .coordinator import TrestDataCoordinator

SENSOR_TYPES: tuple[SensorEntityDescription, ...] = (
    SensorEntityDescription(
        key="battery_discharge",
        name="Battery Discharge",
        device_class=SensorDeviceClass.POWER,
        native_unit_of_measurement="kW",
        icon="mdi:battery-arrow-down",
    ),
    SensorEntityDescription(
        key="battery_charge",
        name="Battery Charge",
        device_class=SensorDeviceClass.POWER,
        native_unit_of_measurement="kW",
        icon="mdi:battery-arrow-up",
    ),
    SensorEntityDescription(
        key="battery_capacity",
        name="Battery Capacity",
        device_class=SensorDeviceClass.BATTERY,
        native_unit_of_measurement="%",
        icon="mdi:battery",
    ),
    SensorEntityDescription(
        key="battery_stored_power",
        name="Battery Stored Power",
        device_class=SensorDeviceClass.ENERGY,
        native_unit_of_measurement="kW",
        icon="mdi:power",
    ),
    SensorEntityDescription(
        key="total_load_active_power",
        name="Total Load Active Power",
        device_class=SensorDeviceClass.POWER,
        native_unit_of_measurement="kW",
        icon="mdi:flash",
    ),
    SensorEntityDescription(
        key="realtime_solar",
        name="Realtime Solar",
        device_class=SensorDeviceClass.POWER,
        native_unit_of_measurement="kW",
        icon="mdi:white-balance-sunny",
    ),
    SensorEntityDescription(
        key="timestamp",
        name="Timestamp",
        device_class=SensorDeviceClass.TIMESTAMP,
        icon="mdi:clock",
    ),
    SensorEntityDescription(
        key="solar_profile",
        name="Solar Profile",
        device_class=SensorDeviceClass.POWER,
        icon="mdi:solar-power",
    ),
    SensorEntityDescription(
        key="daily_yeild",
        name="Daily Yield",
        device_class=SensorDeviceClass.ENERGY,
        native_unit_of_measurement="kW",
        icon="mdi:calendar",
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: TrestConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Add a Trest Solar Controller entry."""
    coordinator: TrestDataCoordinator = entry.runtime_data

    entities = [
        TrestSolarControllerSensor(coordinator, entry.entry_id, description)
        for description in SENSOR_TYPES
    ]

    async_add_entities(entities)


class TrestSolarControllerSensor(CoordinatorEntity[TrestDataCoordinator], SensorEntity):
    """The sensor for Trest Solar Controller."""

    _attr_has_entity_name = True
    entity_description: SensorEntityDescription

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
    def native_value(self) -> str | int | float | datetime | None:
        """Return the state of the sensor."""

        key = self.entity_description.key

        if key == "timestamp":
            timestamp_str = self.coordinator.data.to_dict().get(key)
            if timestamp_str:
                return datetime.fromisoformat(timestamp_str)

        return self.coordinator.data.to_dict().get(key)
