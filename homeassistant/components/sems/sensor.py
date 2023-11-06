"""Sensor for retrieving data for SEMS portal."""

from __future__ import annotations

from typing import Any

from homeassistant.components.sensor import SensorDeviceClass, SensorEntityDescription
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    CURRENCY_DOLLAR,
    PERCENTAGE,
    UnitOfEnergy,
    UnitOfTemperature,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import DOMAIN, SemsDataUpdateCoordinator


class BaseSemsSensor(CoordinatorEntity):
    """Base class for Sems Sensors."""

    _attr_has_entity_name = True

    def __init__(
        self,
        name: str,
        model: str,
        config_entry: ConfigEntry,
        description: SensorEntityDescription,
        coordinator: SemsDataUpdateCoordinator,
    ) -> None:
        """Initialize the sensor."""

        super().__init__(self, coordinator)

        self.deviceName = name
        self.deviceModel = model
        self.coordinator = coordinator
        self._config_entry_id = config_entry.entry_id
        self.entity_description = description
        self._attr_unique_id = f"{name}-{description.key}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, name)},
            manufacturer="Goodwe",
            model=model,
            name=name,
        )


class SemsInformationSensor(BaseSemsSensor):
    """Used to represent a SemsInformationSensor."""

    @property
    def native_value(self):
        """Return the state of the sensor."""
        return self.coordinator.data["powerPlant"]["info"][self.entity_description.key]


class SemsInverterSensor(BaseSemsSensor):
    """Used to represent a SemsInverterSensor."""

    def getInverterByName(
        self, coordinator: SemsDataUpdateCoordinator, name: str
    ) -> Any:
        """Retrieve the inverter by name."""

        for inverter in coordinator.data["powerPlant"]["inverters"]:
            if inverter["name"] == name:
                return inverter
        return None

    @property
    def native_value(self):
        """Return the state of the sensor."""
        return self.getInverterByName(self.coordinator, self.deviceName)[
            self.entity_description.key
        ]


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Get the setup sensor."""

    coordinator: SemsDataUpdateCoordinator = hass.data[DOMAIN][config_entry.entry_id]

    interters = coordinator.data["powerPlant"]["inverters"]

    inverterEntities = [
        SemsInverterSensor(
            inverter["name"], inverter["model"], config_entry, description, coordinator
        )
        for description in SENSOR_TYPES_INVERTERS
        for inverter in interters
    ]

    powerplantName = coordinator.data["powerPlant"]["info"]["name"]
    powerplantModel = coordinator.data["powerPlant"]["info"]["model"]
    powerPlantInformationEntities = [
        SemsInformationSensor(
            powerplantName, powerplantModel, config_entry, description, coordinator
        )
        for description in SENSOR_TYPES_POWERSTATION
    ]

    async_add_entities(inverterEntities)
    async_add_entities(powerPlantInformationEntities)


SENSOR_TYPES_INVERTERS: tuple[SensorEntityDescription, ...] = (
    SensorEntityDescription(
        translation_key="inner_temp",
        key="innerTemp",
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        device_class=SensorDeviceClass.TEMPERATURE,
    ),
)

SENSOR_TYPES_POWERSTATION: tuple[SensorEntityDescription, ...] = (
    SensorEntityDescription(
        translation_key="powerstation_id",
        key="powerstation_id",
        native_unit_of_measurement=None,
        device_class=None,
    ),
    SensorEntityDescription(
        translation_key="station_name",
        key="stationname",
        native_unit_of_measurement=None,
        device_class=None,
    ),
    SensorEntityDescription(
        translation_key="battery_capacity",
        key="battery_capacity",
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
    ),
    SensorEntityDescription(
        translation_key="capacity",
        key="capacity",
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
    ),
    SensorEntityDescription(
        translation_key="month_generation",
        key="monthGeneration",
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
    ),
    SensorEntityDescription(
        translation_key="generation_live",
        key="generationLive",
        native_unit_of_measurement=UnitOfEnergy.WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
    ),
    SensorEntityDescription(
        translation_key="generation_today",
        key="generationToday",
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
    ),
    SensorEntityDescription(
        translation_key="alltime_generation",
        key="allTimeGeneration",
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
    ),
    SensorEntityDescription(
        translation_key="today_income",
        key="todayIncome",
        native_unit_of_measurement=CURRENCY_DOLLAR,
        device_class=SensorDeviceClass.MONETARY,
    ),
    SensorEntityDescription(
        translation_key="total_income",
        key="totalIncome",
        native_unit_of_measurement=CURRENCY_DOLLAR,
        device_class=SensorDeviceClass.MONETARY,
    ),
    SensorEntityDescription(
        translation_key="battery",
        key="battery",
        native_unit_of_measurement=UnitOfEnergy.WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
    ),
    SensorEntityDescription(
        translation_key="battery_status",
        key="batteryStatus",
        native_unit_of_measurement=None,
        device_class=None,
    ),
    SensorEntityDescription(
        translation_key="battery_status_str",
        key="batteryStatusStr",
        native_unit_of_measurement=None,
        device_class=None,
    ),
    SensorEntityDescription(
        translation_key="house_load",
        key="houseLoad",
        native_unit_of_measurement=UnitOfEnergy.WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
    ),
    SensorEntityDescription(
        translation_key="house_load_status",
        key="houseLoadStatus",
        native_unit_of_measurement=None,
        device_class=None,
    ),
    SensorEntityDescription(
        translation_key="grid_load",
        key="gridLoad",
        native_unit_of_measurement=UnitOfEnergy.WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
    ),
    SensorEntityDescription(
        translation_key="grid_load_status",
        key="gridLoadStatus",
        native_unit_of_measurement=None,
        device_class=None,
    ),
    SensorEntityDescription(
        translation_key="soc",
        key="soc",
        native_unit_of_measurement=None,
        device_class=None,
    ),
    SensorEntityDescription(
        translation_key="soc_text",
        key="socText",
        native_unit_of_measurement=PERCENTAGE,
        device_class=None,
    ),
)
