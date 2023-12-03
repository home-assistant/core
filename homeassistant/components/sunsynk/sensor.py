"""Support for Sunsynk sensors."""
from __future__ import annotations

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import PERCENTAGE, EntityCategory, UnitOfEnergy, UnitOfPower
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import (
    BATTERY_POWER,
    BATTERY_SOC,
    DOMAIN,
    GRID_ENERGY_EXPORT_TODAY,
    GRID_ENERGY_EXPORT_TOTAL,
    GRID_ENERGY_IMPORT_TODAY,
    GRID_ENERGY_IMPORT_TOTAL,
    GRID_POWER,
    SOLAR_ENERGY_TODAY,
    SOLAR_ENERGY_TOTAL,
    SOLAR_POWER,
    SUNSYNK_COORDINATOR,
)
from .coordinator import SunsynkCoordinator

SENSOR_TYPES: tuple[SensorEntityDescription, ...] = (
    SensorEntityDescription(
        name="Grid Power",
        key=GRID_POWER,
        device_class=SensorDeviceClass.POWER,
        native_unit_of_measurement=UnitOfPower.WATT,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SensorEntityDescription(
        name="Battery Power",
        key=BATTERY_POWER,
        device_class=SensorDeviceClass.POWER,
        native_unit_of_measurement=UnitOfPower.WATT,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SensorEntityDescription(
        name="Battery Level",
        key=BATTERY_SOC,
        device_class=SensorDeviceClass.BATTERY,
        entity_category=EntityCategory.DIAGNOSTIC,
        native_unit_of_measurement=PERCENTAGE,
    ),
    SensorEntityDescription(
        name="Solar Power",
        key=SOLAR_POWER,
        device_class=SensorDeviceClass.POWER,
        native_unit_of_measurement=UnitOfPower.WATT,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SensorEntityDescription(
        name="Solar Energy Today",
        key=SOLAR_ENERGY_TODAY,
        icon="mdi:solar-power",
        device_class=SensorDeviceClass.ENERGY,
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        state_class=SensorStateClass.TOTAL,
    ),
    SensorEntityDescription(
        name="Solar Energy Total",
        key=SOLAR_ENERGY_TOTAL,
        icon="mdi:solar-power",
        device_class=SensorDeviceClass.ENERGY,
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        state_class=SensorStateClass.TOTAL,
    ),
    SensorEntityDescription(
        name="Grid Import Today",
        key=GRID_ENERGY_IMPORT_TODAY,
        icon="mdi:power-plug",
        device_class=SensorDeviceClass.ENERGY,
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        state_class=SensorStateClass.TOTAL,
    ),
    SensorEntityDescription(
        name="Grid Import Total",
        key=GRID_ENERGY_IMPORT_TOTAL,
        icon="mdi:power-plug",
        device_class=SensorDeviceClass.ENERGY,
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        state_class=SensorStateClass.TOTAL,
    ),
    SensorEntityDescription(
        name="Grid Export Today",
        key=GRID_ENERGY_EXPORT_TODAY,
        icon="mdi:power-plug",
        device_class=SensorDeviceClass.ENERGY,
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        state_class=SensorStateClass.TOTAL,
    ),
    SensorEntityDescription(
        name="Grid Export Total",
        key=GRID_ENERGY_EXPORT_TOTAL,
        icon="mdi:power-plug",
        device_class=SensorDeviceClass.ENERGY,
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        state_class=SensorStateClass.TOTAL,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Add a Sunsynk entry."""

    coordinator: SunsynkCoordinator = hass.data[DOMAIN][entry.entry_id][
        SUNSYNK_COORDINATOR
    ]

    inverters = await coordinator.api.get_inverters()
    for inverter in inverters:
        sensors = [
            SunsynkSensor(coordinator, description, inverter.sn)
            for description in SENSOR_TYPES
        ]

        async_add_entities(sensors)


class SunsynkSensor(CoordinatorEntity[SunsynkCoordinator], SensorEntity):
    """Representation of a grid power usage."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: SunsynkCoordinator,
        description: SensorEntityDescription,
        inverter_sn: str,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        self.entity_description = description
        self.inverter_sn = inverter_sn
        self._attr_unique_id = f"{self.inverter_sn}_{self.entity_description.key}"

    @property
    def device_info(self) -> DeviceInfo:
        """Return the device info."""
        return DeviceInfo(
            identifiers={(DOMAIN, self.inverter_sn)},
            name=f"Inverter {self.inverter_sn}",
            manufacturer="Sunsynk",
        )

    @property
    def native_value(self) -> str | int | float | None:
        """Return the state."""
        return self.coordinator.data[self.inverter_sn][self.entity_description.key]
