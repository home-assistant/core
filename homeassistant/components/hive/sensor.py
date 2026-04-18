"""Support for the Hive sensors."""

from collections.abc import Callable
from dataclasses import dataclass
from datetime import timedelta
from typing import Any

from apyhiveapi import Hive

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import (
    PERCENTAGE,
    EntityCategory,
    UnitOfPower,
    UnitOfTemperature,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.typing import StateType

from . import HiveConfigEntry
from .entity import HiveEntity

PARALLEL_UPDATES = 0
SCAN_INTERVAL = timedelta(seconds=15)


@dataclass(frozen=True)
class HiveSensorEntityDescription(SensorEntityDescription):
    """Describes Hive sensor entity."""

    fn: Callable[[StateType], StateType] = lambda x: x


SENSOR_TYPES: tuple[HiveSensorEntityDescription, ...] = (
    HiveSensorEntityDescription(
        key="Battery",
        native_unit_of_measurement=PERCENTAGE,
        device_class=SensorDeviceClass.BATTERY,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    HiveSensorEntityDescription(
        key="Power",
        native_unit_of_measurement=UnitOfPower.WATT,
        state_class=SensorStateClass.MEASUREMENT,
        device_class=SensorDeviceClass.POWER,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    HiveSensorEntityDescription(
        key="Current_Temperature",
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        state_class=SensorStateClass.MEASUREMENT,
        device_class=SensorDeviceClass.TEMPERATURE,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    HiveSensorEntityDescription(
        key="Heating_Current_Temperature",
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
    ),
    HiveSensorEntityDescription(
        key="Heating_Target_Temperature",
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
    ),
    HiveSensorEntityDescription(
        key="Heating_Mode",
        device_class=SensorDeviceClass.ENUM,
        options=["schedule", "manual", "off"],
        translation_key="heating",
        fn=lambda x: x.lower() if isinstance(x, str) else None,
    ),
    HiveSensorEntityDescription(
        key="Hotwater_Mode",
        device_class=SensorDeviceClass.ENUM,
        options=["schedule", "on", "off"],
        translation_key="hot_water",
        fn=lambda x: x.lower() if isinstance(x, str) else None,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: HiveConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Hive thermostat based on a config entry."""
    hive = entry.runtime_data
    devices = hive.session.deviceList.get("sensor")
    if not devices:
        return
    async_add_entities(
        (
            HiveSensorEntity(hive, dev, description)
            for dev in devices
            for description in SENSOR_TYPES
            if dev["hiveType"] == description.key
        ),
        True,
    )


class HiveSensorEntity(HiveEntity, SensorEntity):
    """Hive Sensor Entity."""

    entity_description: HiveSensorEntityDescription

    def __init__(
        self,
        hive: Hive,
        hive_device: dict[str, Any],
        entity_description: HiveSensorEntityDescription,
    ) -> None:
        """Initialise hive sensor."""
        super().__init__(hive, hive_device)
        self.entity_description = entity_description

    async def async_update(self) -> None:
        """Update all Node data from Hive."""
        await self.hive.session.updateData(self.device)
        self.device = await self.hive.sensor.getSensor(self.device)
        self._attr_native_value = self.entity_description.fn(
            self.device.get("status", {}).get("state")
        )
