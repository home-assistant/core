"""Sensor platform for the Papouch integration."""

from dataclasses import dataclass
import logging
from typing import cast, override

from aiopapouch import PapouchDevice

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import PapouchConfigEntry
from .coordinator import PapouchBaseCoordinator
from .entity import PapouchEntity

PARALLEL_UPDATES = 0
_LOGGER = logging.getLogger(__name__)


@dataclass(frozen=True, kw_only=True)
class PapouchSensorEntityDescription(SensorEntityDescription):
    """Description class of the Papouch sensor."""

    data_key: str = ""
    value_key: str = ""
    item_id: str = ""
    translation_placeholders: dict[str, str] | None = None


SENSOR_TYPES: tuple[PapouchSensorEntityDescription, ...] = (
    PapouchSensorEntityDescription(
        key="temperature",
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    PapouchSensorEntityDescription(
        key="humidity",
        device_class=SensorDeviceClass.HUMIDITY,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    PapouchSensorEntityDescription(
        key="dew_point",
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    PapouchSensorEntityDescription(
        key="co2",
        device_class=SensorDeviceClass.CO2,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    PapouchSensorEntityDescription(
        key="pressure",
        device_class=SensorDeviceClass.ATMOSPHERIC_PRESSURE,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    PapouchSensorEntityDescription(
        key="wind_direction",
        device_class=SensorDeviceClass.WIND_DIRECTION,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    PapouchSensorEntityDescription(
        key="wind_direction_text",  # e.g. N, E, ...
    ),
    PapouchSensorEntityDescription(
        key="wind_speed",
        device_class=SensorDeviceClass.WIND_SPEED,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    PapouchSensorEntityDescription(
        key="rain",
        state_class=SensorStateClass.MEASUREMENT,
    ),
    PapouchSensorEntityDescription(
        key="precipitation_intensity",
        device_class=SensorDeviceClass.PRECIPITATION_INTENSITY,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    PapouchSensorEntityDescription(
        key="counter",
        state_class=SensorStateClass.TOTAL,
    ),
    PapouchSensorEntityDescription(
        key="battery",
        device_class=SensorDeviceClass.BATTERY,
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    PapouchSensorEntityDescription(
        key="signal_strength",
        device_class=SensorDeviceClass.SIGNAL_STRENGTH,
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
)

SENSOR_MAP = {desc.key: desc for desc in SENSOR_TYPES}


def _get_translation_config(
    data_type: str, name_val: str | None
) -> tuple[str | None, dict[str, str] | None]:
    if name_val is not None:
        if data_type == "battery":
            return "batt_custom", {"name": name_val}
        if data_type == "signal_strength":
            return "rssi_custom", {"name": name_val}
        return f"{data_type}_custom", {"name": name_val}

    if data_type == "dew_point":
        return "dew_point", None

    return None, None


async def async_setup_entry(
    hass: HomeAssistant,
    entry: PapouchConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the sensor platform."""
    coordinator = entry.runtime_data
    entities = []

    for device in coordinator.get_devices():
        for sensor_data in device.get_supported_sensors():
            data_type = cast(str, sensor_data.get("data_type"))
            base_desc = SENSOR_MAP.get(data_type)

            if not base_desc:
                _LOGGER.warning("Unknown sensor type '%s'. Skipping entity", data_type)
                continue

            name_val = sensor_data.get("name")
            translation_key, placeholders = _get_translation_config(data_type, name_val)

            description = PapouchSensorEntityDescription(
                key=sensor_data["value_key"],
                data_key=sensor_data["type"],
                value_key=sensor_data["value_key"],
                item_id=str(sensor_data["item_id"]),
                device_class=base_desc.device_class,
                state_class=base_desc.state_class,
                native_unit_of_measurement=sensor_data.get("unit"),
                translation_key=translation_key,
                translation_placeholders=placeholders,
                entity_category=base_desc.entity_category,
            )
            entities.append(PapouchSensor(coordinator, device, description))

    async_add_entities(entities)


class PapouchSensor(PapouchEntity, SensorEntity):
    """Representation of a generic Papouch sensor."""

    entity_description: PapouchSensorEntityDescription

    def __init__(
        self,
        coordinator: PapouchBaseCoordinator,
        device: PapouchDevice,
        description: PapouchSensorEntityDescription,
    ) -> None:
        """Initialize the sensor."""

        super().__init__(coordinator, device)
        self.entity_description = description
        self._attr_unique_id = f"{self.device.conf.identifier}_{description.data_key}_{description.value_key}"

        if description.translation_placeholders:
            self._attr_translation_placeholders = description.translation_placeholders

    @property
    @override
    def native_value(self) -> float | int | None:
        """Return the state of the sensor."""

        device_data = self.coordinator.data[self.device.conf.identifier]

        value = device_data.get(self.entity_description.data_key, {}).get(
            self.entity_description.value_key
        )
        return cast("float | int | None", value)

    @override
    @callback
    def _handle_coordinator_update(self) -> None:
        for sensor_data in self.device.get_supported_sensors():
            if sensor_data.get("value_key") == self.entity_description.value_key:
                if "unit" in sensor_data:
                    self._attr_native_unit_of_measurement = sensor_data["unit"]
                break

        super()._handle_coordinator_update()
