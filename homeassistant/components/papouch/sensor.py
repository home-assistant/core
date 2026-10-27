"""Sensor platform for the Papouch integration."""

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

from . import PapouchConfigEntry, PapouchNetworkDataUpdateCoordinator
from .entity import PapouchEntity

PARALLEL_UPDATES = 0
_LOGGER = logging.getLogger(__name__)

# native_unit_of_measurement is omitted in these static descriptions
# because aiopapouch (device) provides units dynamically per sensor
# it is assigned at runtime in PapouchSensor.__init__
SENSOR_TYPES: tuple[SensorEntityDescription, ...] = (
    SensorEntityDescription(
        key="temperature",
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SensorEntityDescription(
        key="humidity",
        device_class=SensorDeviceClass.HUMIDITY,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SensorEntityDescription(
        key="dew_point",
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SensorEntityDescription(
        key="co2",
        device_class=SensorDeviceClass.CO2,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SensorEntityDescription(
        key="pressure",
        device_class=SensorDeviceClass.ATMOSPHERIC_PRESSURE,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SensorEntityDescription(
        key="wind_direction",
        device_class=SensorDeviceClass.WIND_DIRECTION,
    ),
    SensorEntityDescription(
        key="wind_direction_text",  # e.g. string sent by device
        # we cannot use SensorDeviceClass.ENUM here because the device
        # sends non-standardized strings instead of a fixed list of options
    ),
    SensorEntityDescription(
        key="wind_speed",
        device_class=SensorDeviceClass.WIND_SPEED,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SensorEntityDescription(
        key="rain",
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SensorEntityDescription(
        key="precipitation_intensity",
        device_class=SensorDeviceClass.PRECIPITATION_INTENSITY,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SensorEntityDescription(
        key="counter",
        state_class=SensorStateClass.TOTAL,
    ),
    SensorEntityDescription(
        key="battery",
        device_class=SensorDeviceClass.BATTERY,
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    SensorEntityDescription(
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

    device = coordinator.get_device()

    for sensor_data in device.get_supported_sensors():
        data_type = cast(str, sensor_data.get("data_type"))
        description = SENSOR_MAP.get(data_type)

        if not description:
            _LOGGER.warning("Unknown sensor type '%s'. Skipping entity", data_type)
            continue

        entities.append(
            PapouchSensor(coordinator, device, description, sensor_data, data_type)
        )

    async_add_entities(entities)


class PapouchSensor(PapouchEntity, SensorEntity):
    """Representation of a generic Papouch sensor."""

    entity_description: SensorEntityDescription

    def __init__(
        self,
        coordinator: PapouchNetworkDataUpdateCoordinator,
        device: PapouchDevice,
        description: SensorEntityDescription,
        sensor_data: dict,
        data_type: str,
    ) -> None:
        """Initialize the sensor."""

        super().__init__(coordinator, device)
        self.entity_description = description

        self.data_key = sensor_data["type"]
        self.value_key = sensor_data["value_key"]
        self.item_id = str(sensor_data["item_id"])

        self._attr_unique_id = (
            f"{self.device.conf.identifier}_{self.data_key}_{self.value_key}"
        )
        self._attr_native_unit_of_measurement = sensor_data.get("unit")

        translation_key, placeholders = _get_translation_config(
            data_type, sensor_data.get("name")
        )
        if translation_key:
            self._attr_translation_key = translation_key
        if placeholders:
            self._attr_translation_placeholders = placeholders

    @property
    @override
    def native_value(self) -> float | int | None:
        """Return the state of the sensor."""

        device_data = self.coordinator.data[self.device.conf.identifier]

        value = device_data.get(self.data_key, {}).get(self.value_key)
        return cast("float | int | None", value)

    @override
    @callback
    def _handle_coordinator_update(self) -> None:
        for sensor_data in self.device.get_supported_sensors():
            if sensor_data.get("value_key") == self.value_key:
                if "unit" in sensor_data:
                    self._attr_native_unit_of_measurement = sensor_data["unit"]
                break

        super()._handle_coordinator_update()
