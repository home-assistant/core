"""Definition of air-Q sensor platform."""
from __future__ import annotations

import logging

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    CONCENTRATION_MICROGRAMS_PER_CUBIC_METER,
    CONCENTRATION_MILLIGRAMS_PER_CUBIC_METER,
    CONCENTRATION_PARTS_PER_BILLION,
    CONCENTRATION_PARTS_PER_MILLION,
    PERCENTAGE,
    PRESSURE_HPA,
    SOUND_PRESSURE_WEIGHTED_DBA,
    TEMP_CELSIUS,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import AirQCoordinator
from .const import (
    CONCENTRATION_GRAMS_PER_CUBIC_METER,
    COUNT_PER_DECILITERS,
    DOMAIN,
    LENGTH_MICROMETERS,
    SensorDeviceClass as CustomSensorDeviceClass,
)

_LOGGER = logging.getLogger(__name__)

# Keys must match those in the data dictionary
SENSOR_TYPES: list[SensorEntityDescription] = [
    SensorEntityDescription(
        key="co",
        name="CO",
        device_class=SensorDeviceClass.CO,
        native_unit_of_measurement=CONCENTRATION_MILLIGRAMS_PER_CUBIC_METER,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SensorEntityDescription(
        key="co2",
        name="CO2",
        device_class=SensorDeviceClass.CO2,
        native_unit_of_measurement=CONCENTRATION_PARTS_PER_MILLION,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SensorEntityDescription(
        key="dewpt",
        name="Dew point",
        device_class=CustomSensorDeviceClass.DEWPOINT,
        native_unit_of_measurement=TEMP_CELSIUS,
        state_class=SensorStateClass.MEASUREMENT,
        icon="mdi:water-thermometer",
    ),
    SensorEntityDescription(
        key="h2s",
        name="H2S",
        device_class=CustomSensorDeviceClass.H2S,
        native_unit_of_measurement=CONCENTRATION_MICROGRAMS_PER_CUBIC_METER,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SensorEntityDescription(
        key="health",
        name="Health index",
        device_class=CustomSensorDeviceClass.INDEX_HEALTH,
        state_class=SensorStateClass.MEASUREMENT,
        icon="mdi:heart-pulse",
    ),
    SensorEntityDescription(
        key="humidity",
        name="Humidity",
        device_class=SensorDeviceClass.HUMIDITY,
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SensorEntityDescription(
        key="humidity_abs",
        name="Absolute humidity",
        device_class=CustomSensorDeviceClass.HUMIDITY_ABS,
        native_unit_of_measurement=CONCENTRATION_GRAMS_PER_CUBIC_METER,
        state_class=SensorStateClass.MEASUREMENT,
        icon="mdi:water",
    ),
    SensorEntityDescription(
        key="no2",
        name="NO2",
        device_class=SensorDeviceClass.NITROGEN_DIOXIDE,
        native_unit_of_measurement=CONCENTRATION_MICROGRAMS_PER_CUBIC_METER,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SensorEntityDescription(
        key="o3",
        name="Ozone",
        device_class=SensorDeviceClass.OZONE,
        native_unit_of_measurement=CONCENTRATION_MICROGRAMS_PER_CUBIC_METER,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SensorEntityDescription(
        key="oxygen",
        name="Oxygen",
        device_class=CustomSensorDeviceClass.OXYGEN,
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        icon="mdi:leaf",
    ),
    SensorEntityDescription(
        key="performance",
        name="Performance",
        device_class=CustomSensorDeviceClass.INDEX_PERFORMANCE,
        state_class=SensorStateClass.MEASUREMENT,
        icon="mdi:head-check",
    ),
    SensorEntityDescription(
        key="pm1",
        name="PM1",
        device_class=SensorDeviceClass.PM1,
        native_unit_of_measurement=CONCENTRATION_MICROGRAMS_PER_CUBIC_METER,
        state_class=SensorStateClass.MEASUREMENT,
        icon="mdi:dots-hexagon",
    ),
    SensorEntityDescription(
        key="pm2_5",
        name="PM2.5",
        device_class=SensorDeviceClass.PM25,
        native_unit_of_measurement=CONCENTRATION_MICROGRAMS_PER_CUBIC_METER,
        state_class=SensorStateClass.MEASUREMENT,
        icon="mdi:dots-hexagon",
    ),
    SensorEntityDescription(
        key="pm10",
        name="PM10",
        device_class=SensorDeviceClass.PM10,
        native_unit_of_measurement=CONCENTRATION_MICROGRAMS_PER_CUBIC_METER,
        state_class=SensorStateClass.MEASUREMENT,
        icon="mdi:dots-hexagon",
    ),
    SensorEntityDescription(
        key="cnt0_3",
        name="Particulates count 0.3",
        device_class=CustomSensorDeviceClass.CNT0_3,
        native_unit_of_measurement=COUNT_PER_DECILITERS,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SensorEntityDescription(
        key="cnt0_5",
        name="Particulates count 0.5",
        device_class=CustomSensorDeviceClass.CNT0_5,
        native_unit_of_measurement=COUNT_PER_DECILITERS,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SensorEntityDescription(
        key="cnt1",
        name="Particulates count 1",
        device_class=CustomSensorDeviceClass.CNT1,
        native_unit_of_measurement=COUNT_PER_DECILITERS,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SensorEntityDescription(
        key="cnt2_5",
        name="Particulates count 2.5",
        device_class=CustomSensorDeviceClass.CNT2_5,
        native_unit_of_measurement=COUNT_PER_DECILITERS,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SensorEntityDescription(
        key="cnt5",
        name="Particulates count 5",
        device_class=CustomSensorDeviceClass.CNT5,
        native_unit_of_measurement=COUNT_PER_DECILITERS,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SensorEntityDescription(
        key="cnt10",
        name="Particulates count 10",
        device_class=CustomSensorDeviceClass.CNT10,
        native_unit_of_measurement=COUNT_PER_DECILITERS,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SensorEntityDescription(
        key="TypPS",
        name="Mean particulates size",
        device_class=CustomSensorDeviceClass.MEAN_PM_SIZE,
        native_unit_of_measurement=LENGTH_MICROMETERS,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SensorEntityDescription(
        key="pressure",
        name="Pressure",
        device_class=SensorDeviceClass.PRESSURE,
        native_unit_of_measurement=PRESSURE_HPA,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SensorEntityDescription(
        key="so2",
        name="SO2",
        device_class=SensorDeviceClass.SULPHUR_DIOXIDE,
        native_unit_of_measurement=CONCENTRATION_MICROGRAMS_PER_CUBIC_METER,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SensorEntityDescription(
        key="sound",
        name="Sound",
        device_class=CustomSensorDeviceClass.SOUND,
        native_unit_of_measurement=SOUND_PRESSURE_WEIGHTED_DBA,
        state_class=SensorStateClass.MEASUREMENT,
        icon="mdi:ear-hearing",
    ),
    SensorEntityDescription(
        key="sound_max",
        name="Loudest sound during the averaging interval",
        device_class=CustomSensorDeviceClass.SOUND,
        native_unit_of_measurement=SOUND_PRESSURE_WEIGHTED_DBA,
        state_class=SensorStateClass.MEASUREMENT,
        icon="mdi:ear-hearing",
    ),
    SensorEntityDescription(
        key="temperature",
        name="Temperature",
        device_class=SensorDeviceClass.TEMPERATURE,
        native_unit_of_measurement=TEMP_CELSIUS,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SensorEntityDescription(
        key="tvoc",
        name="VOC",
        device_class=SensorDeviceClass.VOLATILE_ORGANIC_COMPOUNDS,
        native_unit_of_measurement=CONCENTRATION_PARTS_PER_BILLION,
        state_class=SensorStateClass.MEASUREMENT,
    ),
]


async def async_setup_entry(
    hass: HomeAssistant,
    config: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up sensor entities based on a config entry."""

    coordinator = hass.data[DOMAIN][config.entry_id]
    available_keys = list(coordinator.data.keys())

    # Add sensors under warmup
    status = coordinator.data["Status"]
    if isinstance(status, dict):
        warming_up_sensors = [
            k for k, v in status.items() if "sensor still in warm up phase" in v
        ]
        available_keys.extend(warming_up_sensors)
        _LOGGER.debug(
            "Following %d sensors are warming up: %s",
            len(warming_up_sensors),
            ", ".join(warming_up_sensors),
        )

    # Filter out non-sensor keys and build a list of SensorEntityDescription objects
    available_sensors = [
        description for description in SENSOR_TYPES if description.key in available_keys
    ]
    _LOGGER.debug(
        "Identified %d  available sensors: %s",
        len(available_sensors),
        ", ".join([sensor.key for sensor in available_sensors]),
    )

    entities = [
        AirQSensor(coordinator, description) for description in available_sensors
    ]
    async_add_entities(entities)


class AirQSensor(CoordinatorEntity, SensorEntity):
    """Representation of a Sensor."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: AirQCoordinator,
        description: SensorEntityDescription,
    ) -> None:
        """Initialize a single sensor."""
        super().__init__(coordinator)
        self.entity_description = description

        # device_info["name"] (e.g. ABC) will be prepended to description.name: 'ABC O3'
        self._attr_device_info = coordinator.device_info
        self._attr_name = description.name
        self._attr_unique_id = f"{coordinator.device_id}_{description.key}"

    @property
    def native_value(self) -> float | int | None:
        """Return the value reported by the sensor."""
        # While a sensor is warming up its key isn't present in the returned dict
        # => .get(key) returns None
        return self.coordinator.data.get(self.entity_description.key)
