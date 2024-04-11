"""Sensor platform for Pinecil integration."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import (
    PERCENTAGE,
    UnitOfElectricPotential,
    UnitOfPower,
    UnitOfTemperature,
    UnitOfTime,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import CONNECTION_BLUETOOTH, DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import StateType
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import PinecilConfigEntry
from .const import (
    DOMAIN,
    MANUFACTURER,
    MODEL,
    OHM,
    OPERATING_MODES,
    POWER_SOURCES,
    PinecilEntity,
)
from .coordinator import PinecilCoordinator


@dataclass(frozen=True, kw_only=True)
class PinecilSensorEntityDescription(SensorEntityDescription):
    """Describes Pinecil sensor entity."""

    value_fn: Callable[[Any], Any]


SENSOR_DESCRIPTIONS: tuple[PinecilSensorEntityDescription, ...] = (
    PinecilSensorEntityDescription(
        key=PinecilEntity.LIVE_TEMP,
        translation_key=PinecilEntity.LIVE_TEMP,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda data: data.get("LiveTemp"),
    ),
    PinecilSensorEntityDescription(
        key=PinecilEntity.DC_VOLTAGE,
        translation_key=PinecilEntity.DC_VOLTAGE,
        native_unit_of_measurement=UnitOfElectricPotential.VOLT,
        device_class=SensorDeviceClass.VOLTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda data: data.get("Voltage") / 10,
    ),
    PinecilSensorEntityDescription(
        key=PinecilEntity.HANDLETEMP,
        translation_key=PinecilEntity.HANDLETEMP,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda data: data.get("HandleTemp") / 10,
    ),
    PinecilSensorEntityDescription(
        key=PinecilEntity.PWMLEVEL,
        translation_key=PinecilEntity.PWMLEVEL,
        native_unit_of_measurement=PERCENTAGE,
        suggested_display_precision=0,
        device_class=SensorDeviceClass.POWER_FACTOR,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda data: data.get("PWMLevel") * 100 / 255.0,
    ),
    PinecilSensorEntityDescription(
        key=PinecilEntity.POWER_SRC,
        translation_key=PinecilEntity.POWER_SRC,
        device_class=SensorDeviceClass.ENUM,
        options=POWER_SOURCES,
        value_fn=lambda data: POWER_SOURCES[data.get("PowerSource")],
    ),
    PinecilSensorEntityDescription(
        key=PinecilEntity.TIP_RESISTANCE,
        translation_key=PinecilEntity.TIP_RESISTANCE,
        native_unit_of_measurement=OHM,
        value_fn=lambda data: data.get("TipResistance") / 10,
    ),
    PinecilSensorEntityDescription(
        key=PinecilEntity.UPTIME,
        translation_key=PinecilEntity.UPTIME,
        native_unit_of_measurement=UnitOfTime.SECONDS,
        device_class=SensorDeviceClass.DURATION,
        state_class=SensorStateClass.TOTAL_INCREASING,
        value_fn=lambda data: int(data.get("Uptime") / 10),
    ),
    PinecilSensorEntityDescription(
        key=PinecilEntity.MOVEMENT_TIME,
        translation_key=PinecilEntity.MOVEMENT_TIME,
        native_unit_of_measurement=UnitOfTime.MILLISECONDS,
        device_class=SensorDeviceClass.DURATION,
        state_class=SensorStateClass.TOTAL_INCREASING,
        value_fn=lambda data: int(data.get("MovementTime") / 10),
    ),
    PinecilSensorEntityDescription(
        key=PinecilEntity.MAX_TIP_TEMP_ABILITY,
        translation_key=PinecilEntity.MAX_TIP_TEMP_ABILITY,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        device_class=SensorDeviceClass.TEMPERATURE,
        icon="mdi:thermometer-alert",
        value_fn=lambda data: data.get("MaxTipTempAbility"),
    ),
    PinecilSensorEntityDescription(
        key=PinecilEntity.TIP_VOLTAGE,
        translation_key=PinecilEntity.TIP_VOLTAGE,
        native_unit_of_measurement=UnitOfElectricPotential.MILLIVOLT,
        device_class=SensorDeviceClass.VOLTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=3,
        value_fn=lambda data: data.get("uVoltsTip") / 1000,
    ),
    PinecilSensorEntityDescription(
        key=PinecilEntity.HALL_SENSOR,
        translation_key=PinecilEntity.HALL_SENSOR,
        state_class=SensorStateClass.MEASUREMENT,
        entity_registry_enabled_default=False,
        value_fn=lambda data: data.get("HallSensor"),
    ),
    PinecilSensorEntityDescription(
        key=PinecilEntity.OPERATING_MODE,
        translation_key=PinecilEntity.OPERATING_MODE,
        device_class=SensorDeviceClass.ENUM,
        options=OPERATING_MODES,
        value_fn=lambda data: OPERATING_MODES[data.get("OperatingMode")],
    ),
    PinecilSensorEntityDescription(
        key=PinecilEntity.ESTIMATED_POWER,
        translation_key=PinecilEntity.ESTIMATED_POWER,
        native_unit_of_measurement=UnitOfPower.WATT,
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda data: data.get("Watts") / 10,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: PinecilConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up sensors from a config entry."""
    coordinator = entry.runtime_data

    async_add_entities(
        PinecilSensor(coordinator, description, entry)
        for description in SENSOR_DESCRIPTIONS
    )


class PinecilSensor(CoordinatorEntity, SensorEntity):
    """Implementation of a Pinecil sensor."""

    _attr_has_entity_name = True
    entity_description: PinecilSensorEntityDescription

    def __init__(
        self,
        coordinator: PinecilCoordinator,
        entity_description: PinecilSensorEntityDescription,
        entry: PinecilConfigEntry,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        assert entry.unique_id
        self.entity_description = entity_description
        self._attr_unique_id = f"{entry.unique_id}_{entity_description.key}"
        self.device_info = DeviceInfo(
            identifiers={(DOMAIN, entry.unique_id)},
            connections={(CONNECTION_BLUETOOTH, entry.unique_id)},
            manufacturer=MANUFACTURER,
            model=MODEL,
            name="Pinecil",
            sw_version=coordinator.device.get("build"),
        )

    @property
    def native_value(self) -> StateType:
        """Return sensor state."""
        return self.entity_description.value_fn(self.coordinator.data)
