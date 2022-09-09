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
    ACTIVITY_BECQUEREL_PER_CUBIC_METER,
    CONCENTRATION_GRAMS_PER_CUBIC_METER,
    DOMAIN,
    SensorDeviceClass as CustomSensorDeviceClass,
)

_LOGGER = logging.getLogger(__name__)

# Keys must match those in the data dictionary
SENSOR_TYPES: list[SensorEntityDescription] = [
    SensorEntityDescription(
        key="nh3_MR100",
        name="Ammonia",
        device_class=CustomSensorDeviceClass.AMMONIA,
        native_unit_of_measurement=CONCENTRATION_MICROGRAMS_PER_CUBIC_METER,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SensorEntityDescription(
        key="cl2_M20",
        name="Chlorine",
        device_class=CustomSensorDeviceClass.CHLORINE,
        native_unit_of_measurement=CONCENTRATION_MICROGRAMS_PER_CUBIC_METER,
        state_class=SensorStateClass.MEASUREMENT,
    ),
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
        key="ethanol",
        name="Ethanol",
        device_class=CustomSensorDeviceClass.ETHANOL,
        native_unit_of_measurement=CONCENTRATION_MICROGRAMS_PER_CUBIC_METER,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SensorEntityDescription(
        key="ch2o_M10",
        name="Formaldehyde",
        device_class=CustomSensorDeviceClass.FORMALDEHYDE,
        native_unit_of_measurement=CONCENTRATION_MICROGRAMS_PER_CUBIC_METER,
        state_class=SensorStateClass.MEASUREMENT,
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
        name="Health Index",
        device_class=CustomSensorDeviceClass.INDEX_HEALTH,
        native_unit_of_measurement=PERCENTAGE,
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
        key="h2_M1000",
        name="Hydrogen",
        device_class=CustomSensorDeviceClass.HYDROGEN,
        native_unit_of_measurement=CONCENTRATION_MICROGRAMS_PER_CUBIC_METER,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SensorEntityDescription(
        key="ch4_MIPEX",
        name="Methane",
        device_class=CustomSensorDeviceClass.METHANE,
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SensorEntityDescription(
        key="n2o",
        name="N2O",
        device_class=SensorDeviceClass.NITROUS_OXIDE,
        native_unit_of_measurement=CONCENTRATION_MICROGRAMS_PER_CUBIC_METER,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SensorEntityDescription(
        key="no_M250",
        name="NO",
        device_class=SensorDeviceClass.NITROGEN_MONOXIDE,
        native_unit_of_measurement=CONCENTRATION_MICROGRAMS_PER_CUBIC_METER,
        state_class=SensorStateClass.MEASUREMENT,
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
        name="Performance Index",
        device_class=CustomSensorDeviceClass.INDEX_PERFORMANCE,
        native_unit_of_measurement=PERCENTAGE,
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
        key="pressure",
        name="Pressure",
        device_class=SensorDeviceClass.PRESSURE,
        native_unit_of_measurement=PRESSURE_HPA,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SensorEntityDescription(
        key="pressure_rel",
        name="Relative pressure",
        device_class=CustomSensorDeviceClass.PRESSURE_REL,
        native_unit_of_measurement=PRESSURE_HPA,
        state_class=SensorStateClass.MEASUREMENT,
        icon="mdi:gauge",
    ),
    SensorEntityDescription(
        key="c3h8_MIPEX",
        name="Propane",
        device_class=CustomSensorDeviceClass.PROPANE,
        native_unit_of_measurement=PERCENTAGE,
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
        name="Noise",
        device_class=CustomSensorDeviceClass.SOUND,
        native_unit_of_measurement=SOUND_PRESSURE_WEIGHTED_DBA,
        state_class=SensorStateClass.MEASUREMENT,
        icon="mdi:ear-hearing",
    ),
    SensorEntityDescription(
        key="sound_max",
        name="Noise (Maximum)",
        device_class=CustomSensorDeviceClass.SOUND,
        native_unit_of_measurement=SOUND_PRESSURE_WEIGHTED_DBA,
        state_class=SensorStateClass.MEASUREMENT,
        icon="mdi:ear-hearing",
    ),
    SensorEntityDescription(
        key="radon",
        name="Radon",
        device_class=CustomSensorDeviceClass.RADON,
        native_unit_of_measurement=ACTIVITY_BECQUEREL_PER_CUBIC_METER,
        state_class=SensorStateClass.MEASUREMENT,
        icon="mdi:radioactive",
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
    SensorEntityDescription(
        key="tvoc_ionsc",
        name="VOC (Industrial)",
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

        self._attr_device_info = coordinator.device_info
        self._attr_name = description.name
        self._attr_unique_id = f"{coordinator.device_id}_{description.key}"
        # the following two sensor units must be converted to %
        self._factor = 0.1 if description.key in ["performance", "health"] else 1.0

    @property
    def native_value(self) -> float | int | None:
        """Return the value reported by the sensor."""
        # While a sensor is warming up its key isn't present in the returned dict
        value = self.coordinator.data.get(self.entity_description.key)
        return value * self._factor if value else value
