"""Support for INDI Allsky sensors."""

from collections.abc import Callable
from contextlib import suppress
from dataclasses import dataclass
from typing import Any, override

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import (
    DEGREE,
    PERCENTAGE,
    EntityCategory,
    UnitOfElectricCurrent,
    UnitOfElectricPotential,
    UnitOfPower,
    UnitOfPressure,
    UnitOfSpeed,
    UnitOfTemperature,
    UnitOfTime,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.typing import StateType

from .coordinator import (
    IndiAllSkyConfigEntry,
    IndiAllSkyData,
    IndiAllSkyDataUpdateCoordinator,
)
from .entity import IndiAllSkyEntity

PARALLEL_UPDATES = 0


def _get_user_slot_value(data: IndiAllSkyData, index: int) -> float | None:
    """Extract sensor value strictly from raw_user array index."""
    if (
        not data.sensor
        or not data.sensor.raw_user
        or len(data.sensor.raw_user) <= index
    ):
        return None

    item = data.sensor.raw_user[index]
    res = item.get("value") if isinstance(item, dict) else item
    if res is not None:
        with suppress(ValueError, TypeError):
            return float(res)

    return None


def _get_cpu_temp_value(data: IndiAllSkyData) -> float | None:
    """Extract CPU temperature strictly from raw_temp slot index 10."""
    if not data.sensor or not data.sensor.raw_temp or len(data.sensor.raw_temp) <= 10:
        return None

    item = data.sensor.raw_temp[10]
    res = item.get("value") if isinstance(item, dict) else item
    if res is not None:
        with suppress(ValueError, TypeError):
            val = float(res)
            if val > 0:
                return round(val, 1)

    return None


@dataclass(frozen=True, kw_only=True)
class IndiAllSkySensorEntityDescription(SensorEntityDescription):
    """Class describing INDI Allsky hardware sensor entities."""

    value_fn: Callable[[IndiAllSkyData], StateType]


PREDEFINED_SENSOR_DESCRIPTIONS: tuple[IndiAllSkySensorEntityDescription, ...] = (
    IndiAllSkySensorEntityDescription(
        key="dew_heater",
        translation_key="dew_heater",
        icon="mdi:heating-coil",
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda data: _get_user_slot_value(data, 1),
    ),
    IndiAllSkySensorEntityDescription(
        key="dewpoint",
        translation_key="dewpoint",
        device_class=SensorDeviceClass.TEMPERATURE,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda data: _get_user_slot_value(data, 2),
    ),
    IndiAllSkySensorEntityDescription(
        key="frost_point",
        translation_key="frost_point",
        device_class=SensorDeviceClass.TEMPERATURE,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda data: _get_user_slot_value(data, 3),
    ),
    IndiAllSkySensorEntityDescription(
        key="fan_duty_cycle",
        translation_key="fan_duty_cycle",
        icon="mdi:fan",
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda data: _get_user_slot_value(data, 4),
    ),
    IndiAllSkySensorEntityDescription(
        key="heat_index",
        translation_key="heat_index",
        device_class=SensorDeviceClass.TEMPERATURE,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda data: _get_user_slot_value(data, 5),
    ),
    IndiAllSkySensorEntityDescription(
        key="wind_direction",
        translation_key="wind_direction",
        device_class=SensorDeviceClass.WIND_DIRECTION,
        native_unit_of_measurement=DEGREE,
        state_class=SensorStateClass.MEASUREMENT_ANGLE,
        value_fn=lambda data: _get_user_slot_value(data, 6),
    ),
    IndiAllSkySensorEntityDescription(
        key="device_sqm",
        translation_key="device_sqm",
        icon="mdi:weather-night",
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda data: _get_user_slot_value(data, 7),
    ),
    IndiAllSkySensorEntityDescription(
        key="camera_sqm",
        translation_key="camera_sqm",
        icon="mdi:weather-night",
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda data: _get_user_slot_value(data, 8),
    ),
    IndiAllSkySensorEntityDescription(
        key="camera_sqm_adu",
        translation_key="camera_sqm_adu",
        icon="mdi:counter",
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda data: _get_user_slot_value(data, 9),
    ),
    IndiAllSkySensorEntityDescription(
        key="cpu_temperature",
        translation_key="cpu_temperature",
        device_class=SensorDeviceClass.TEMPERATURE,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        value_fn=_get_cpu_temp_value,
    ),
)


IGNORED_DYNAMIC_KEYS: set[str] = {
    "adu",
    "analog_to_digital_unit",
    "binmode",
    "binning_mode",
    "camera_sensor_temp",
    "camera_sqm",
    "camera_sqm_adu",
    "camera_sqm_magnitude",
    "camera_temp",
    "cpu_temp",
    "cpu_temperature",
    "device_sqm",
    "device_sqm_magnitude",
    "dew_heater",
    "dew_heater_duty_cycle",
    "dew_heater_level",
    "dew_heater_output",
    "dew_point",
    "dewpoint",
    "exposure",
    "exposure_time",
    "fan_duty_cycle",
    "fan_level",
    "fan_speed",
    "fan_speed_level",
    "fan_state",
    "filename",
    "frost_point",
    "gain",
    "heat_index",
    "night",
    "sky_quality",
    "sqm",
    "sqm_adu",
    "stars",
    "temp",
    "wind_dir",
    "wind_direction",
}


def _infer_sensor_metadata(
    key: str,
    raw_name: str | None,
    raw_device_class: str | None,
    raw_unit: str | None,
) -> tuple[str, SensorDeviceClass | None, str | None, SensorStateClass | None]:
    """Infer entity name, device class, native unit, and state class for dynamic hardware sensors."""
    device_class: SensorDeviceClass | None = None
    state_class: SensorStateClass | None = SensorStateClass.MEASUREMENT

    if raw_device_class:
        with suppress(ValueError):
            device_class = SensorDeviceClass(raw_device_class.lower())

    unit = raw_unit
    key_lower = key.lower()
    name_str = raw_name or key.replace("_", " ").capitalize()
    name_lower = name_str.lower()

    if device_class is None:
        if any(
            x in key_lower or x in name_lower
            for x in (
                "temperature",
                "temp",
                "dewpoint",
                "dew_point",
                "heat_index",
                "frost_point",
            )
        ):
            device_class = SensorDeviceClass.TEMPERATURE
        elif "humidity" in key_lower or "humidity" in name_lower:
            device_class = SensorDeviceClass.HUMIDITY
        elif "pressure" in key_lower or "pressure" in name_lower:
            device_class = SensorDeviceClass.PRESSURE
        elif (
            "wind_speed" in key_lower
            or "wind_speed" in name_lower
            or "wind_gust" in key_lower
        ):
            device_class = SensorDeviceClass.WIND_SPEED
        elif "wind_direction" in key_lower or "wind_dir" in name_lower:
            device_class = SensorDeviceClass.WIND_DIRECTION
        elif "voltage" in key_lower or "volt" in name_lower:
            device_class = SensorDeviceClass.VOLTAGE
        elif "current" in key_lower or "amp" in name_lower:
            device_class = SensorDeviceClass.CURRENT
        elif "power" in key_lower or "watt" in name_lower:
            device_class = SensorDeviceClass.POWER
        elif "lux" in key_lower or "illuminance" in name_lower:
            device_class = SensorDeviceClass.ILLUMINANCE
        elif "duration" in key_lower:
            device_class = SensorDeviceClass.DURATION

    if unit is None:
        if device_class == SensorDeviceClass.TEMPERATURE:
            unit = UnitOfTemperature.CELSIUS
        elif device_class == SensorDeviceClass.HUMIDITY:
            unit = PERCENTAGE
        elif device_class == SensorDeviceClass.PRESSURE:
            unit = UnitOfPressure.HPA
        elif device_class == SensorDeviceClass.WIND_SPEED:
            unit = UnitOfSpeed.METERS_PER_SECOND
        elif device_class == SensorDeviceClass.WIND_DIRECTION:
            unit = DEGREE
        elif device_class == SensorDeviceClass.VOLTAGE:
            unit = UnitOfElectricPotential.VOLT
        elif device_class == SensorDeviceClass.CURRENT:
            unit = UnitOfElectricCurrent.AMPERE
        elif device_class == SensorDeviceClass.POWER:
            unit = UnitOfPower.WATT
        elif device_class == SensorDeviceClass.DURATION:
            unit = UnitOfTime.SECONDS

    if device_class == SensorDeviceClass.WIND_DIRECTION:
        state_class = SensorStateClass.MEASUREMENT_ANGLE

    return name_str, device_class, unit, state_class


async def async_setup_entry(
    hass: HomeAssistant,
    entry: IndiAllSkyConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up INDI Allsky sensors based on a config entry."""
    coordinator = entry.runtime_data

    # Always register predefined hardware & CPU sensors
    entities: list[SensorEntity] = [
        IndiAllSkySensor(coordinator, entry, description)
        for description in PREDEFINED_SENSOR_DESCRIPTIONS
    ]

    registered_keys: set[str] = {
        desc.key for desc in PREDEFINED_SENSOR_DESCRIPTIONS
    } | IGNORED_DYNAMIC_KEYS

    @callback
    def _async_update_hardware_sensors() -> None:
        """Register newly discovered hardware sensors from coordinator data."""
        if not coordinator.data.sensor:
            return

        new_entities: list[SensorEntity] = []
        sensors_dict = coordinator.data.sensor.sensors or {}

        # Process items in sensors dictionary
        for key in sensors_dict:
            if key in registered_keys:
                continue
            registered_keys.add(key)
            new_entities.append(
                IndiAllSkyDynamicHardwareSensor(coordinator, entry, key)
            )

        if new_entities:
            async_add_entities(new_entities)

    _async_update_hardware_sensors()
    entry.async_on_unload(
        coordinator.async_add_listener(_async_update_hardware_sensors)
    )

    async_add_entities(entities)


class IndiAllSkySensor(IndiAllSkyEntity, SensorEntity):
    """Representation of an INDI Allsky predefined sensor."""

    entity_description: IndiAllSkySensorEntityDescription

    def __init__(
        self,
        coordinator: IndiAllSkyDataUpdateCoordinator,
        entry: IndiAllSkyConfigEntry,
        description: IndiAllSkySensorEntityDescription,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator, entry)
        self.entity_description = description
        self._attr_unique_id = f"{entry.entry_id}_{description.key}"

    @property
    @override
    def native_value(self) -> StateType:
        """Return the state of the sensor."""
        return self.entity_description.value_fn(self.coordinator.data)


class IndiAllSkyDynamicHardwareSensor(IndiAllSkyEntity, SensorEntity):
    """Representation of a dynamic hardware sensor exposed by INDI Allsky."""

    def __init__(
        self,
        coordinator: IndiAllSkyDataUpdateCoordinator,
        entry: IndiAllSkyConfigEntry,
        sensor_key: str,
    ) -> None:
        """Initialize the dynamic hardware sensor."""
        super().__init__(coordinator, entry)
        self._sensor_key = sensor_key
        self._attr_unique_id = f"{entry.entry_id}_{sensor_key}"

        self._update_attributes()

    def _get_sensor_item(self) -> Any:
        if self.coordinator.data.sensor and isinstance(
            self.coordinator.data.sensor.sensors, dict
        ):
            return self.coordinator.data.sensor.sensors.get(self._sensor_key)
        return None

    def _update_attributes(self) -> None:
        item = self._get_sensor_item()
        raw_name: str | None = None
        raw_device_class: str | None = None
        raw_unit: str | None = None

        if isinstance(item, dict):
            raw_name = item.get("name") or item.get("label")
            raw_device_class = item.get("device_class")
            raw_unit = item.get("unit")

        name_str, device_class, unit, state_class = _infer_sensor_metadata(
            self._sensor_key, raw_name, raw_device_class, raw_unit
        )

        if "translation_key" not in self.__dict__ and not hasattr(
            self, "_attr_translation_key"
        ):
            self._attr_name = name_str

        self._attr_device_class = device_class
        self._attr_native_unit_of_measurement = unit
        self._attr_state_class = state_class

    @property
    @override
    def native_value(self) -> StateType:
        """Return the state of the sensor."""
        if not self.coordinator.data.sensor:
            return None

        item = self._get_sensor_item()
        if item is not None:
            if isinstance(item, dict):
                val = item.get("value")
            else:
                val = item
            if val is not None:
                with suppress(ValueError, TypeError):
                    return float(val)
                return str(val)

        return None
