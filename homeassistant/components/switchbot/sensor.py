"""Support for SwitchBot sensors."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

import switchbot
from switchbot import AirQualityLevel, HumidifierWaterLevel, SwitchbotModel

from homeassistant.components.bluetooth import async_last_service_info
from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import (
    CONCENTRATION_MICROGRAMS_PER_CUBIC_METER,
    CONCENTRATION_PARTS_PER_MILLION,
    LIGHT_LUX,
    PERCENTAGE,
    SIGNAL_STRENGTH_DECIBELS_MILLIWATT,
    EntityCategory,
    UnitOfElectricCurrent,
    UnitOfElectricPotential,
    UnitOfEnergy,
    UnitOfPower,
    UnitOfTemperature,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import AIRPURIFIER_PM25_MODELS, DOMAIN
from .coordinator import SwitchbotConfigEntry, SwitchbotDataUpdateCoordinator
from .entity import SwitchbotEntity

PARALLEL_UPDATES = 0


@dataclass(frozen=True, kw_only=True)
class SwitchBotSensorEntityDescription(SensorEntityDescription):
    """Describes SwitchBot sensor entities with optional value transformation."""

    value_fn: Callable[[str | int | None], str | int | None] = lambda v: v


SENSOR_TYPES: dict[str, SwitchBotSensorEntityDescription] = {
    "rssi": SwitchBotSensorEntityDescription(
        key="rssi",
        translation_key="bluetooth_signal",
        native_unit_of_measurement=SIGNAL_STRENGTH_DECIBELS_MILLIWATT,
        device_class=SensorDeviceClass.SIGNAL_STRENGTH,
        state_class=SensorStateClass.MEASUREMENT,
        entity_registry_enabled_default=False,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    "wifi_rssi": SwitchBotSensorEntityDescription(
        key="wifi_rssi",
        translation_key="wifi_signal",
        native_unit_of_measurement=SIGNAL_STRENGTH_DECIBELS_MILLIWATT,
        device_class=SensorDeviceClass.SIGNAL_STRENGTH,
        state_class=SensorStateClass.MEASUREMENT,
        entity_registry_enabled_default=False,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    "battery": SwitchBotSensorEntityDescription(
        key="battery",
        native_unit_of_measurement=PERCENTAGE,
        device_class=SensorDeviceClass.BATTERY,
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    "co2": SwitchBotSensorEntityDescription(
        key="co2",
        native_unit_of_measurement=CONCENTRATION_PARTS_PER_MILLION,
        state_class=SensorStateClass.MEASUREMENT,
        device_class=SensorDeviceClass.CO2,
    ),
    "lightLevel": SwitchBotSensorEntityDescription(
        key="lightLevel",
        translation_key="light_level",
        state_class=SensorStateClass.MEASUREMENT,
    ),
    "humidity": SwitchBotSensorEntityDescription(
        key="humidity",
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        device_class=SensorDeviceClass.HUMIDITY,
    ),
    "illuminance": SwitchBotSensorEntityDescription(
        key="illuminance",
        native_unit_of_measurement=LIGHT_LUX,
        state_class=SensorStateClass.MEASUREMENT,
        device_class=SensorDeviceClass.ILLUMINANCE,
    ),
    "temperature": SwitchBotSensorEntityDescription(
        key="temperature",
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        state_class=SensorStateClass.MEASUREMENT,
        device_class=SensorDeviceClass.TEMPERATURE,
    ),
    "power": SwitchBotSensorEntityDescription(
        key="power",
        native_unit_of_measurement=UnitOfPower.WATT,
        state_class=SensorStateClass.MEASUREMENT,
        device_class=SensorDeviceClass.POWER,
    ),
    "current": SwitchBotSensorEntityDescription(
        key="current",
        native_unit_of_measurement=UnitOfElectricCurrent.AMPERE,
        state_class=SensorStateClass.MEASUREMENT,
        device_class=SensorDeviceClass.CURRENT,
    ),
    "voltage": SwitchBotSensorEntityDescription(
        key="voltage",
        native_unit_of_measurement=UnitOfElectricPotential.VOLT,
        state_class=SensorStateClass.MEASUREMENT,
        device_class=SensorDeviceClass.VOLTAGE,
    ),
    "aqi_level": SwitchBotSensorEntityDescription(
        key="aqi_level",
        translation_key="aqi_quality_level",
        device_class=SensorDeviceClass.ENUM,
        options=[member.name.lower() for member in AirQualityLevel],
    ),
    "energy": SwitchBotSensorEntityDescription(
        key="energy",
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        state_class=SensorStateClass.TOTAL_INCREASING,
        device_class=SensorDeviceClass.ENERGY,
    ),
    "water_level": SwitchBotSensorEntityDescription(
        key="water_level",
        translation_key="water_level",
        device_class=SensorDeviceClass.ENUM,
        options=HumidifierWaterLevel.get_levels(),
    ),
    "battery_range": SwitchBotSensorEntityDescription(
        key="battery_range",
        translation_key="battery_range",
        device_class=SensorDeviceClass.ENUM,
        options=["critical", "low", "medium", "high"],
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda v: {
            "<10%": "critical",
            "10-19%": "low",
            "20-59%": "medium",
            ">=60%": "high",
        }.get(str(v)),
    ),
    "pm25": SwitchBotSensorEntityDescription(
        key="pm25",
        native_unit_of_measurement=CONCENTRATION_MICROGRAMS_PER_CUBIC_METER,
        state_class=SensorStateClass.MEASUREMENT,
        device_class=SensorDeviceClass.PM25,
    ),
}


async def async_setup_entry(
    hass: HomeAssistant,
    entry: SwitchbotConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Switchbot sensor based on a config entry."""
    coordinator = entry.runtime_data
    parsed_data = coordinator.device.parsed_data
    sensor_entities: list[SensorEntity] = []
    if isinstance(coordinator.device, switchbot.SwitchbotRelaySwitch2PM):
        sensor_entities.extend(
            SwitchBotSensor(coordinator, sensor, channel)
            for channel in range(1, coordinator.device.channel + 1)
            for sensor in coordinator.device.get_parsed_data(channel)
            if sensor in SENSOR_TYPES
        )
    elif coordinator.model == SwitchbotModel.PRESENCE_SENSOR:
        sensor_entities.extend(
            SwitchBotSensor(coordinator, sensor)
            for sensor in (
                *(
                    s
                    for s in parsed_data
                    if s in SENSOR_TYPES and s not in ("battery", "battery_range")
                ),
                "battery_range",
            )
        )
        if "battery" in parsed_data:
            sensor_entities.append(SwitchBotSensor(coordinator, "battery"))
    else:
        sensors: set[str] = {sensor for sensor in parsed_data if sensor in SENSOR_TYPES}
        if (
            isinstance(coordinator.device, switchbot.SwitchbotAirPurifier)
            and coordinator.model in AIRPURIFIER_PM25_MODELS
        ):
            sensors.add("pm25")
        sensor_entities.extend(
            SwitchBotSensor(coordinator, sensor) for sensor in sensors
        )
    sensor_entities.append(SwitchbotRSSISensor(coordinator, "rssi"))
    async_add_entities(sensor_entities)


class SwitchBotSensor(SwitchbotEntity, SensorEntity):
    """Representation of a Switchbot sensor."""

    entity_description: SwitchBotSensorEntityDescription

    def __init__(
        self,
        coordinator: SwitchbotDataUpdateCoordinator,
        sensor: str,
        channel: int | None = None,
    ) -> None:
        """Initialize the Switchbot sensor."""
        super().__init__(coordinator)
        self._sensor = sensor
        self._channel = channel
        self.entity_description = SENSOR_TYPES[sensor]

        if channel:
            self._attr_unique_id = f"{coordinator.base_unique_id}-{sensor}-{channel}"
            self._attr_device_info = DeviceInfo(
                identifiers={
                    (DOMAIN, f"{coordinator.base_unique_id}-channel-{channel}")
                },
                manufacturer="SwitchBot",
                model_id="RelaySwitch2PM",
                name=f"{coordinator.device_name} Channel {channel}",
            )
        else:
            self._attr_unique_id = f"{coordinator.base_unique_id}-{sensor}"

    @property
    def native_value(self) -> str | int | None:
        """Return the state of the sensor."""
        return self.entity_description.value_fn(self.parsed_data.get(self._sensor))


class SwitchbotRSSISensor(SwitchBotSensor):
    """Representation of a Switchbot RSSI sensor."""

    @property
    def native_value(self) -> str | int | None:
        """Return the state of the sensor."""
        # Switchbot supports both connectable and non-connectable devices
        # so we need to request the rssi value based on the connectable instead
        # of the nearest scanner since that is the RSSI that matters for controlling
        # the device.
        if service_info := async_last_service_info(
            self.hass, self._address, self.coordinator.connectable
        ):
            return service_info.rssi
        return None
