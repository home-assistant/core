"""Sensor platform for the Nature Remo integration."""

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from typing import override

from aionatureremo import (
    APPLIANCE_TYPE_SMART_METER,
    EVENT_HUMIDITY,
    EVENT_ILLUMINATION,
    EVENT_MOVEMENT,
    EVENT_TEMPERATURE,
    Device,
    SmartMeter,
)

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import PERCENTAGE, UnitOfEnergy, UnitOfPower, UnitOfTemperature
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.typing import StateType

from .coordinator import NatureRemoConfigEntry, NatureRemoCoordinator
from .entity import NatureRemoApplianceEntity, NatureRemoDeviceEntity

PARALLEL_UPDATES = 0


def _event_value(device: Device, key: str) -> float | None:
    """Return the value of a device event, if present."""
    event = device.events.get(key)
    return event.value if event else None


def _event_timestamp(device: Device, key: str) -> datetime | None:
    """Return the timestamp of a device event, if present."""
    event = device.events.get(key)
    return event.created_at if event else None


@dataclass(frozen=True, kw_only=True)
class NatureRemoDeviceSensorDescription(SensorEntityDescription):
    """Describes a sensor derived from a Remo device event."""

    event_key: str
    value_fn: Callable[[Device], StateType | datetime]


DEVICE_SENSORS: tuple[NatureRemoDeviceSensorDescription, ...] = (
    NatureRemoDeviceSensorDescription(
        key="temperature",
        event_key=EVENT_TEMPERATURE,
        device_class=SensorDeviceClass.TEMPERATURE,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=1,
        value_fn=lambda device: _event_value(device, EVENT_TEMPERATURE),
    ),
    NatureRemoDeviceSensorDescription(
        key="humidity",
        event_key=EVENT_HUMIDITY,
        device_class=SensorDeviceClass.HUMIDITY,
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=0,
        value_fn=lambda device: _event_value(device, EVENT_HUMIDITY),
    ),
    NatureRemoDeviceSensorDescription(
        # Deliberately no device_class and no native_unit_of_measurement:
        # Nature reports an uncalibrated relative illumination value, not
        # lux, so ILLUMINANCE + lx would assert a unit the hardware does
        # not provide.
        key="illuminance",
        event_key=EVENT_ILLUMINATION,
        translation_key="illuminance",
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda device: _event_value(device, EVENT_ILLUMINATION),
    ),
    NatureRemoDeviceSensorDescription(
        key="last_motion",
        event_key=EVENT_MOVEMENT,
        translation_key="last_motion",
        device_class=SensorDeviceClass.TIMESTAMP,
        value_fn=lambda device: _event_timestamp(device, EVENT_MOVEMENT),
    ),
)


@dataclass(frozen=True, kw_only=True)
class NatureRemoSmartMeterSensorDescription(SensorEntityDescription):
    """Describes a sensor derived from smart meter properties."""

    value_fn: Callable[[SmartMeter], StateType]


SMART_METER_SENSORS: tuple[NatureRemoSmartMeterSensorDescription, ...] = (
    NatureRemoSmartMeterSensorDescription(
        key="instantaneous_power",
        device_class=SensorDeviceClass.POWER,
        native_unit_of_measurement=UnitOfPower.WATT,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda meter: meter.instantaneous_power_w,
    ),
    NatureRemoSmartMeterSensorDescription(
        key="cumulative_energy_normal",
        translation_key="cumulative_energy_normal",
        device_class=SensorDeviceClass.ENERGY,
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        state_class=SensorStateClass.TOTAL_INCREASING,
        value_fn=lambda meter: meter.cumulative_energy_kwh,
    ),
    NatureRemoSmartMeterSensorDescription(
        key="cumulative_energy_reverse",
        translation_key="cumulative_energy_reverse",
        device_class=SensorDeviceClass.ENERGY,
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        state_class=SensorStateClass.TOTAL_INCREASING,
        value_fn=lambda meter: meter.cumulative_energy_reverse_kwh,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: NatureRemoConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up sensors for the devices and smart meters present at setup."""
    coordinator = entry.runtime_data
    data = coordinator.data
    # A Remo only gets the sensors matching the events it reports.
    entities: list[SensorEntity] = [
        NatureRemoDeviceSensor(coordinator, device_id, description)
        for device_id, device in data.devices.items()
        for description in DEVICE_SENSORS
        if description.event_key in device.events
    ]
    # Smart meters only get the ECHONET properties they publish.
    for appliance_id, appliance in data.appliances.items():
        if (
            appliance.type != APPLIANCE_TYPE_SMART_METER
            or appliance.smart_meter is None
        ):
            continue
        entities.extend(
            NatureRemoSmartMeterSensor(coordinator, appliance_id, description)
            for description in SMART_METER_SENSORS
            if description.value_fn(appliance.smart_meter) is not None
        )
    async_add_entities(entities)


class NatureRemoDeviceSensor(NatureRemoDeviceEntity, SensorEntity):
    """A sensor backed by a Remo device event."""

    entity_description: NatureRemoDeviceSensorDescription

    def __init__(
        self,
        coordinator: NatureRemoCoordinator,
        device_id: str,
        description: NatureRemoDeviceSensorDescription,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator, device_id)
        self.entity_description = description
        self._attr_unique_id = f"{device_id}_{description.key}"

    @property
    @override
    def native_value(self) -> StateType | datetime:
        """Return the current value."""
        return self.entity_description.value_fn(self.device)


class NatureRemoSmartMeterSensor(NatureRemoApplianceEntity, SensorEntity):
    """A sensor backed by an ECHONET Lite smart meter property."""

    entity_description: NatureRemoSmartMeterSensorDescription

    def __init__(
        self,
        coordinator: NatureRemoCoordinator,
        appliance_id: str,
        description: NatureRemoSmartMeterSensorDescription,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator, appliance_id)
        self.entity_description = description
        self._attr_unique_id = f"{appliance_id}_{description.key}"

    @property
    @override
    def native_value(self) -> StateType:
        """Return the current value."""
        meter = self.appliance.smart_meter
        if meter is None:
            return None
        return self.entity_description.value_fn(meter)
