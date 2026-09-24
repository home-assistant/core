"""Support for INDI Allsky sensors."""

from collections.abc import Callable
from contextlib import suppress
from dataclasses import dataclass
import re
from typing import Any, override

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import (
    DEGREE,
    LIGHT_LUX,
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


@dataclass(frozen=True, kw_only=True)
class IndiAllSkySensorEntityDescription(SensorEntityDescription):
    """Class describing INDI Allsky hardware sensor entities."""

    value_fn: Callable[[IndiAllSkyData], StateType]


PREDEFINED_SENSOR_DESCRIPTIONS: tuple[IndiAllSkySensorEntityDescription, ...] = (
    IndiAllSkySensorEntityDescription(
        key="binmode",
        translation_key="binmode",
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        value_fn=lambda data: data.exposure.binmode if data.exposure else None,
    ),
    IndiAllSkySensorEntityDescription(
        key="exposure",
        translation_key="exposure",
        device_class=SensorDeviceClass.DURATION,
        native_unit_of_measurement=UnitOfTime.SECONDS,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda data: data.exposure.exposure if data.exposure else None,
    ),
    IndiAllSkySensorEntityDescription(
        key="filename",
        translation_key="filename",
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        value_fn=lambda data: data.exposure.filename if data.exposure else None,
    ),
    IndiAllSkySensorEntityDescription(
        key="gain",
        translation_key="gain",
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        value_fn=lambda data: data.exposure.gain if data.exposure else None,
    ),
    IndiAllSkySensorEntityDescription(
        key="sqm",
        translation_key="sqm",
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda data: data.exposure.sqm if data.exposure else None,
    ),
    IndiAllSkySensorEntityDescription(
        key="stars",
        translation_key="stars",
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda data: data.exposure.stars if data.exposure else None,
    ),
    IndiAllSkySensorEntityDescription(
        key="camera_sensor_temp",
        translation_key="camera_sensor_temp",
        device_class=SensorDeviceClass.TEMPERATURE,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda data: data.exposure.temp if data.exposure else None,
    ),
    IndiAllSkySensorEntityDescription(
        key="dew_heater",
        translation_key="dew_heater",
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda data: data.sensor.dew_heater if data.sensor else None,
    ),
    IndiAllSkySensorEntityDescription(
        key="dewpoint",
        translation_key="dewpoint",
        device_class=SensorDeviceClass.TEMPERATURE,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda data: data.sensor.dew_point if data.sensor else None,
    ),
    IndiAllSkySensorEntityDescription(
        key="frost_point",
        translation_key="frost_point",
        device_class=SensorDeviceClass.TEMPERATURE,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda data: data.sensor.frost_point if data.sensor else None,
    ),
    IndiAllSkySensorEntityDescription(
        key="fan_duty_cycle",
        translation_key="fan_duty_cycle",
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda data: data.sensor.fan_duty_cycle if data.sensor else None,
    ),
    IndiAllSkySensorEntityDescription(
        key="heat_index",
        translation_key="heat_index",
        device_class=SensorDeviceClass.TEMPERATURE,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda data: data.sensor.heat_index if data.sensor else None,
    ),
    IndiAllSkySensorEntityDescription(
        key="wind_direction",
        translation_key="wind_direction",
        device_class=SensorDeviceClass.WIND_DIRECTION,
        native_unit_of_measurement=DEGREE,
        state_class=SensorStateClass.MEASUREMENT_ANGLE,
        value_fn=lambda data: data.sensor.wind_direction if data.sensor else None,
    ),
    IndiAllSkySensorEntityDescription(
        key="device_sqm",
        translation_key="device_sqm",
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda data: data.sensor.device_sqm if data.sensor else None,
    ),
    IndiAllSkySensorEntityDescription(
        key="camera_sqm",
        translation_key="camera_sqm",
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda data: data.sensor.camera_sqm if data.sensor else None,
    ),
    IndiAllSkySensorEntityDescription(
        key="camera_sqm_adu",
        translation_key="camera_sqm_adu",
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda data: data.sensor.camera_sqm_adu if data.sensor else None,
    ),
    IndiAllSkySensorEntityDescription(
        key="cpu_temperature",
        translation_key="cpu_temperature",
        device_class=SensorDeviceClass.TEMPERATURE,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        value_fn=lambda data: data.sensor.cpu_temperature if data.sensor else None,
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


DEVICE_CLASS_KEYWORDS: tuple[tuple[tuple[str, ...], SensorDeviceClass], ...] = (
    (
        ("temperature", "temp", "dewpoint", "dew point", "heat index", "frost point"),
        SensorDeviceClass.TEMPERATURE,
    ),
    (("humidity",), SensorDeviceClass.HUMIDITY),
    (("pressure",), SensorDeviceClass.PRESSURE),
    (("wind speed", "wind gust"), SensorDeviceClass.WIND_SPEED),
    (("wind direction", "wind dir"), SensorDeviceClass.WIND_DIRECTION),
    (("voltage", "volt"), SensorDeviceClass.VOLTAGE),
    (("current", "amp"), SensorDeviceClass.CURRENT),
    (("power", "watt"), SensorDeviceClass.POWER),
    (("lux", "illuminance"), SensorDeviceClass.ILLUMINANCE),
    (("duration",), SensorDeviceClass.DURATION),
)

DEVICE_CLASS_DEFAULT_UNITS: dict[SensorDeviceClass, str] = {
    SensorDeviceClass.TEMPERATURE: UnitOfTemperature.CELSIUS,
    SensorDeviceClass.HUMIDITY: PERCENTAGE,
    SensorDeviceClass.PRESSURE: UnitOfPressure.HPA,
    SensorDeviceClass.WIND_SPEED: UnitOfSpeed.METERS_PER_SECOND,
    SensorDeviceClass.WIND_DIRECTION: DEGREE,
    SensorDeviceClass.VOLTAGE: UnitOfElectricPotential.VOLT,
    SensorDeviceClass.CURRENT: UnitOfElectricCurrent.AMPERE,
    SensorDeviceClass.POWER: UnitOfPower.WATT,
    SensorDeviceClass.DURATION: UnitOfTime.SECONDS,
    SensorDeviceClass.ILLUMINANCE: LIGHT_LUX,
}

KNOWN_TRANSLATION_KEYS: set[str] = {
    "ambient_temperature",
    "humidity",
    "pressure",
}


def _infer_sensor_metadata(
    key: str,
    raw_name: str | None,
    raw_device_class: str | None,
    raw_unit: str | None,
) -> tuple[str, SensorDeviceClass | None, str | None, SensorStateClass | None]:
    """Infer entity name, device class, native unit, and state class for dynamic hardware sensors."""
    device_class: SensorDeviceClass | None = None

    if raw_device_class:
        with suppress(ValueError):
            device_class = SensorDeviceClass(raw_device_class.lower())

    name_str = raw_name or key.replace("_", " ").capitalize()
    tokens = re.findall(r"[a-z0-9]+", f"{key} {name_str}".lower())
    normalized_phrase = f" {' '.join(tokens)} "

    if device_class is None:
        for keywords, candidate_class in DEVICE_CLASS_KEYWORDS:
            if any(f" {kw} " in normalized_phrase for kw in keywords):
                device_class = candidate_class
                break

    unit = raw_unit or (
        DEVICE_CLASS_DEFAULT_UNITS.get(device_class) if device_class else None
    )

    if device_class == SensorDeviceClass.WIND_DIRECTION:
        state_class = SensorStateClass.MEASUREMENT_ANGLE
    elif device_class is not None or unit is not None:
        state_class = SensorStateClass.MEASUREMENT
    else:
        state_class = None

    return name_str, device_class, unit, state_class


async def async_setup_entry(
    hass: HomeAssistant,
    entry: IndiAllSkyConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up INDI Allsky sensors based on a config entry."""
    coordinator = entry.runtime_data

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

        if self._sensor_key in KNOWN_TRANSLATION_KEYS:
            self._attr_translation_key = self._sensor_key
        elif "translation_key" not in self.__dict__ and not hasattr(
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
                if self.state_class is None:
                    return str(val)
                return None

        return None
