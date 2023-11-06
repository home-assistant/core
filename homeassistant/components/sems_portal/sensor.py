"""Sensor for retrieving data for SEMS portal."""

from __future__ import annotations

from typing import Any

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
)
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

from . import DOMAIN, SemsDataUpdateCoordinator


class SemsInformationSensor(SensorEntity):
    """Used to represent a SemsSensor."""

    _attr_has_entity_name = True

    entity_description: SensorEntityDescription

    def __init__(
        self,
        config_entry: ConfigEntry,
        description: SensorEntityDescription,
        coordinator: SemsDataUpdateCoordinator,
    ) -> None:
        """Initialize the sensor."""

        self.coordinator = coordinator
        deviceName = coordinator.data["powerPlant"]["info"]["name"]
        deviceModel = coordinator.data["powerPlant"]["info"]["model"]
        self._config_entry_id = config_entry.entry_id
        self.entity_description = description
        self._attr_unique_id = f"{deviceName}-{description.key}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, deviceName)},
            manufacturer="Goodwe",
            model=deviceModel,
            name=deviceName,
        )

    @property
    def native_value(self):
        """Return the state of the sensor."""
        return self.coordinator.data["powerPlant"]["info"][self.entity_description.key]

    async def async_added_to_hass(self) -> None:
        """Connect to dispatcher listening for entity data notifications."""
        self.async_on_remove(
            self.coordinator.async_add_listener(self.async_write_ha_state)
        )

    async def async_update(self) -> None:
        """Get the latest data from OWM and updates the states."""
        await self.coordinator.async_request_refresh()


class SemsInverterSensor(SensorEntity):
    """Used to represent a SemsSensor."""

    _attr_has_entity_name = True

    entity_description: SensorEntityDescription

    def getInverterByName(
        self, coordinator: SemsDataUpdateCoordinator, name: str
    ) -> Any:
        """Retrieve the inverter by name."""

        for inverter in coordinator.data["powerPlant"]["inverters"]:
            if inverter["name"] == name:
                return inverter
        return None

    def __init__(
        self,
        name: str,
        model: str,
        config_entry: ConfigEntry,
        description: SensorEntityDescription,
        coordinator: SemsDataUpdateCoordinator,
    ) -> None:
        """Initialize the sensor."""

        self.coordinator = coordinator
        self.deviceName = name
        deviceName = self.deviceName
        deviceModel = model
        self._config_entry_id = config_entry.entry_id
        self.entity_description = description
        self._attr_unique_id = f"{deviceName}-{description.key}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, deviceName)},
            manufacturer="Goodwe",
            model=deviceModel,
            name=deviceName,
        )

    @property
    def native_value(self):
        """Return the state of the sensor."""
        return self.getInverterByName(self.coordinator, self.deviceName)[
            self.entity_description.key
        ]

    async def async_added_to_hass(self) -> None:
        """Connect to dispatcher listening for entity data notifications."""
        self.async_on_remove(
            self.coordinator.async_add_listener(self.async_write_ha_state)
        )

    async def async_update(self) -> None:
        """Get the latest data from OWM and updates the states."""
        await self.coordinator.async_request_refresh()


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

    powerPlantInformationEntities = [
        SemsInformationSensor(config_entry, description, coordinator)
        for description in SENSOR_TYPES_POWERSTATION
    ]

    async_add_entities(inverterEntities)
    async_add_entities(powerPlantInformationEntities)


SENSOR_TYPES_INVERTERS: tuple[SensorEntityDescription, ...] = (
    SensorEntityDescription(
        name="Inner Temp",
        key="innerTemp",
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        device_class=SensorDeviceClass.TEMPERATURE,
    ),
)

SENSOR_TYPES_POWERSTATION: tuple[SensorEntityDescription, ...] = (
    SensorEntityDescription(
        name="Powerstation Id",
        key="powerstation_id",
        native_unit_of_measurement=None,
        device_class=None,
    ),
    SensorEntityDescription(
        name="Station Name",
        key="stationname",
        native_unit_of_measurement=None,
        device_class=None,
    ),
    SensorEntityDescription(
        name="Battery Capacity",
        key="battery_capacity",
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
    ),
    SensorEntityDescription(
        name="Capacity",
        key="capacity",
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
    ),
    SensorEntityDescription(
        name="Month Generation",
        key="monthGeneration",
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
    ),
    SensorEntityDescription(
        name="Generation Live",
        key="generationLive",
        native_unit_of_measurement=UnitOfEnergy.WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
    ),
    SensorEntityDescription(
        name="Generation Today",
        key="generationToday",
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
    ),
    SensorEntityDescription(
        name="All Time Generation",
        key="allTimeGeneration",
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
    ),
    SensorEntityDescription(
        name="Today Income",
        key="todayIncome",
        native_unit_of_measurement=CURRENCY_DOLLAR,
        device_class=SensorDeviceClass.MONETARY,
    ),
    SensorEntityDescription(
        name="Total Income",
        key="totalIncome",
        native_unit_of_measurement=CURRENCY_DOLLAR,
        device_class=SensorDeviceClass.MONETARY,
    ),
    SensorEntityDescription(
        name="Battery",
        key="battery",
        native_unit_of_measurement=UnitOfEnergy.WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
    ),
    SensorEntityDescription(
        name="Battery Status",
        key="batteryStatus",
        native_unit_of_measurement=None,
        device_class=None,
    ),
    SensorEntityDescription(
        name="Battery Status Str",
        key="batteryStatusStr",
        native_unit_of_measurement=None,
        device_class=None,
    ),
    SensorEntityDescription(
        name="House Load",
        key="houseLoad",
        native_unit_of_measurement=UnitOfEnergy.WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
    ),
    SensorEntityDescription(
        name="House Load Status",
        key="houseLoadStatus",
        native_unit_of_measurement=None,
        device_class=None,
    ),
    SensorEntityDescription(
        name="Grid Load",
        key="gridLoad",
        native_unit_of_measurement=UnitOfEnergy.WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
    ),
    SensorEntityDescription(
        name="Grid Load Status",
        key="gridLoadStatus",
        native_unit_of_measurement=None,
        device_class=None,
    ),
    SensorEntityDescription(
        name="Soc", key="soc", native_unit_of_measurement=None, device_class=None
    ),
    SensorEntityDescription(
        name="Soc Text",
        key="socText",
        native_unit_of_measurement=PERCENTAGE,
        device_class=None,
    ),
)
