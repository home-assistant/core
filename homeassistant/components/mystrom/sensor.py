"""Support for myStrom sensors of switches/plugs."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any

from pymystrom.pir import MyStromPir
from pymystrom.switch import MyStromSwitch

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import (
    LIGHT_LUX,
    EntityCategory,
    UnitOfEnergy,
    UnitOfPower,
    UnitOfTemperature,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import CONNECTION_NETWORK_MAC, DeviceInfo
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.util.dt import utcnow

from .const import DOMAIN, MANUFACTURER
from .models import MyStromConfigEntry


@dataclass(frozen=True, kw_only=True)
class MyStromSensorEntityDescription[_DeviceT](SensorEntityDescription):
    """Class describing mystrom sensor entities."""

    value_fn: Callable[[_DeviceT], float | None]


SENSOR_TYPES_PIR: tuple[MyStromSensorEntityDescription[MyStromPir], ...] = (
    MyStromSensorEntityDescription(
        key="temperature",
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        value_fn=(
            lambda device: (
                float(device.temperature_compensated)
                if device.temperature_compensated is not None
                else None
            )
        ),
    ),
    MyStromSensorEntityDescription(
        key="illuminance",
        device_class=SensorDeviceClass.ILLUMINANCE,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=LIGHT_LUX,
        value_fn=(
            lambda device: (
                float(device.intensity) if device.intensity is not None else None
            )
        ),
    ),
)


SENSOR_TYPES_SWITCH: tuple[MyStromSensorEntityDescription[MyStromSwitch], ...] = (
    MyStromSensorEntityDescription(
        key="avg_consumption",
        translation_key="avg_consumption",
        device_class=SensorDeviceClass.POWER,
        native_unit_of_measurement=UnitOfPower.WATT,
        value_fn=lambda device: device.consumedWs,
    ),
    MyStromSensorEntityDescription(
        key="consumption",
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfPower.WATT,
        value_fn=lambda device: device.consumption,
    ),
    MyStromSensorEntityDescription(
        key="energy_since_boot",
        translation_key="energy_since_boot",
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
        native_unit_of_measurement=UnitOfEnergy.JOULE,
        suggested_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        value_fn=lambda device: device.energy_since_boot,
    ),
    MyStromSensorEntityDescription(
        key="temperature",
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        value_fn=lambda device: device.temperature,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: MyStromConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the myStrom entities."""
    device = entry.runtime_data.device
    info = entry.runtime_data.info

    entities: list[MyStromSensorBase] = []
    match device:
        case MyStromPir():
            entities = [
                MyStromSensor(device, entry.title, description, info["mac"])
                for description in SENSOR_TYPES_PIR
                if description.value_fn(device) is not None
            ]
        case MyStromSwitch():
            entities = [
                MyStromSensor(device, entry.title, description, info["mac"])
                for description in SENSOR_TYPES_SWITCH
                if description.value_fn(device) is not None
            ]
            if device.time_since_boot is not None:
                entities.append(
                    MyStromSwitchUptimeSensor(device, entry.title, info["mac"])
                )
        case _:
            entities = []

    async_add_entities(entities)


class MyStromSensorBase(SensorEntity):
    """Base class for myStrom sensors."""

    _attr_has_entity_name = True

    def __init__(
        self,
        device: MyStromSwitch,
        name: str,
        key: str,
        mac: str,
    ) -> None:
        """Initialize the sensor."""
        self.device = device
        self._attr_unique_id = f"{mac}-{key}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, mac)},
            connections={(CONNECTION_NETWORK_MAC, mac)},
            name=name,
            manufacturer=MANUFACTURER,
            sw_version=getattr(device, "firmware", None),
        )


class MyStromSensor[_DeviceT](MyStromSensorBase):
    """Representation of the consumption or temperature of a myStrom switch/plug."""

    entity_description: MyStromSensorEntityDescription[_DeviceT]

    _attr_has_entity_name = True

    def __init__(
        self,
        device: _DeviceT,
        name: str,
        description: MyStromSensorEntityDescription[_DeviceT],
        mac: str,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(device, name, description.key, mac)
        self.entity_description = description

    @property
    def native_value(self) -> float | None:
        """Return the value of the sensor."""
        return self.entity_description.value_fn(self.device)


class MyStromSwitchUptimeSensor(MyStromSensorBase):
    """Representation of a MyStrom Switch uptime sensor."""

    entity_description = SensorEntityDescription(
        key="time_since_boot",
        device_class=SensorDeviceClass.TIMESTAMP,
        entity_category=EntityCategory.DIAGNOSTIC,
        translation_key="time_since_boot",
    )

    def __init__(
        self,
        device: MyStromSwitch,
        name: str,
        mac: str,
    ) -> None:
        """Initialize the uptime sensor."""
        super().__init__(device, name, self.entity_description.key, mac)
        self._last_value: datetime | None = None
        self._last_attributes: dict[str, Any] = {}

    @property
    def native_value(self) -> datetime | None:
        """Return the uptime of the device as a datetime."""

        if self.device.time_since_boot is None or self.device.boot_id is None:
            return None

        # Return cached value if boot_id hasn't changed
        if (
            self._last_value is not None
            and self._last_attributes.get("boot_id") == self.device.boot_id
        ):
            return self._last_value

        self._last_value = utcnow() - timedelta(seconds=self.device.time_since_boot)

        return self._last_value

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return the optional state attributes."""

        self._last_attributes = {
            "boot_id": self.device.boot_id,
        }

        return self._last_attributes
