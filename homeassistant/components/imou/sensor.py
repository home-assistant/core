"""Support for Imou sensor entities."""

from dataclasses import dataclass
from typing import override

from pyimouapi.const import PARAM_STATE_VARIANT, STATE_VARIANT_NUMERIC
from pyimouapi.ha_device import ImouHaDevice

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import (
    PERCENTAGE,
    EntityCategory,
    UnitOfElectricCurrent,
    UnitOfElectricPotential,
    UnitOfEnergy,
    UnitOfPower,
    UnitOfTemperature,
    UnitOfTime,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.typing import StateType

from .const import PARAM_STATE, PARAM_STATUS, imou_device_identifier
from .coordinator import ImouConfigEntry, ImouDataUpdateCoordinator
from .entity import ImouEntity

PARALLEL_UPDATES = 0

STATUS_OPTIONS = ["online", "offline", "sleep", "upgrading"]


@dataclass(frozen=True, kw_only=True)
class ImouSensorEntityDescription(SensorEntityDescription):
    """Describes an Imou sensor entity."""


SENSOR_DESCRIPTIONS: dict[str, ImouSensorEntityDescription] = {
    PARAM_STATUS: ImouSensorEntityDescription(
        key=PARAM_STATUS,
        translation_key=PARAM_STATUS,
        device_class=SensorDeviceClass.ENUM,
        entity_category=EntityCategory.DIAGNOSTIC,
        options=STATUS_OPTIONS,
    ),
    "battery": ImouSensorEntityDescription(
        key="battery",
        device_class=SensorDeviceClass.BATTERY,
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
        suggested_display_precision=0,
    ),
    "storage_used": ImouSensorEntityDescription(
        key="storage_used",
        translation_key="storage_used",
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
        suggested_display_precision=0,
    ),
    "temperature_current": ImouSensorEntityDescription(
        key="temperature_current",
        device_class=SensorDeviceClass.TEMPERATURE,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=1,
    ),
    "humidity_current": ImouSensorEntityDescription(
        key="humidity_current",
        device_class=SensorDeviceClass.HUMIDITY,
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=1,
    ),
    "power": ImouSensorEntityDescription(
        key="power",
        device_class=SensorDeviceClass.POWER,
        native_unit_of_measurement=UnitOfPower.WATT,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    "voltage": ImouSensorEntityDescription(
        key="voltage",
        device_class=SensorDeviceClass.VOLTAGE,
        native_unit_of_measurement=UnitOfElectricPotential.VOLT,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    "current": ImouSensorEntityDescription(
        key="current",
        device_class=SensorDeviceClass.CURRENT,
        native_unit_of_measurement=UnitOfElectricCurrent.AMPERE,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    "switch_cnt": ImouSensorEntityDescription(
        key="switch_cnt",
        translation_key="switch_cnt",
        state_class=SensorStateClass.TOTAL,
    ),
    "use_electricity": ImouSensorEntityDescription(
        key="use_electricity",
        translation_key="use_electricity",
        device_class=SensorDeviceClass.ENERGY,
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        state_class=SensorStateClass.TOTAL_INCREASING,
    ),
    "use_time": ImouSensorEntityDescription(
        key="use_time",
        translation_key="use_time",
        device_class=SensorDeviceClass.DURATION,
        native_unit_of_measurement=UnitOfTime.MINUTES,
        state_class=SensorStateClass.TOTAL_INCREASING,
    ),
}


def _iter_sensors(
    coordinator: ImouDataUpdateCoordinator,
) -> list[tuple[ImouSensorEntityDescription, ImouHaDevice]]:
    """Return (description, device) pairs for supported sensors."""
    return [
        (SENSOR_DESCRIPTIONS[sensor_type], device)
        for device in coordinator.devices
        for sensor_type in device.sensors
        if sensor_type in SENSOR_DESCRIPTIONS
    ]


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ImouConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Imou sensor entities."""
    coordinator = entry.runtime_data

    def _add_sensors(new_devices: list[ImouHaDevice]) -> None:
        device_keys = {imou_device_identifier(device) for device in new_devices}
        async_add_entities(
            ImouSensor(coordinator, description, device)
            for description, device in _iter_sensors(coordinator)
            if imou_device_identifier(device) in device_keys
        )

    coordinator.new_device_callbacks.append(_add_sensors)

    @callback
    def _remove_new_device_callback() -> None:
        if _add_sensors in coordinator.new_device_callbacks:
            coordinator.new_device_callbacks.remove(_add_sensors)

    entry.async_on_unload(_remove_new_device_callback)
    _add_sensors(coordinator.devices)


class ImouSensor(ImouEntity, SensorEntity):
    """Imou sensor entity."""

    entity_description: ImouSensorEntityDescription

    @property
    def _is_numeric_variant(self) -> bool:
        """Return True when the sensor value is numeric."""
        return (
            self.device.sensors[self._entity_type].get(PARAM_STATE_VARIANT)
            == STATE_VARIANT_NUMERIC
        )

    @property
    @override
    def native_value(self) -> StateType:
        """Return the sensor value.

        Numeric sensors only expose numeric values; error codes such as
        storage_used e1/e2 become None (unknown) instead of mixing enum states.
        """
        value = self.device.sensors[self._entity_type][PARAM_STATE]
        if self.entity_description.device_class == SensorDeviceClass.ENUM:
            return value
        if not self._is_numeric_variant:
            return None
        return value
