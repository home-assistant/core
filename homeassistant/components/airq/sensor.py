"""Definition of air-Q sensor platform."""
from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
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
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import AirQCoordinator
from .const import (
    ACTIVITY_BECQUEREL_PER_CUBIC_METER,
    CONCENTRATION_GRAMS_PER_CUBIC_METER,
    DOMAIN,
)

_LOGGER = logging.getLogger(__name__)


@dataclass
class AirQEntityDescriptionMixin:
    """Class for keys required by AirQ entity."""

    value: Callable[[dict], float | int | None]


@dataclass
class AirQEntityDescription(SensorEntityDescription, AirQEntityDescriptionMixin):
    """Describes AirQ sensor entity."""


# Keys must match those in the data dictionary
SENSOR_TYPES: list[AirQEntityDescription] = [
    AirQEntityDescription(
        key="ammonia",
        name="Ammonia",
        native_unit_of_measurement=CONCENTRATION_MICROGRAMS_PER_CUBIC_METER,
        state_class=SensorStateClass.MEASUREMENT,
        value=lambda data: data.get("nh3_MR100"),
    ),
    AirQEntityDescription(
        key="chlorine",
        name="Chlorine",
        native_unit_of_measurement=CONCENTRATION_MICROGRAMS_PER_CUBIC_METER,
        state_class=SensorStateClass.MEASUREMENT,
        value=lambda data: data.get("cl2_M20"),
    ),
    AirQEntityDescription(
        key="co",
        name="CO",
        device_class=SensorDeviceClass.CO,
        native_unit_of_measurement=CONCENTRATION_MILLIGRAMS_PER_CUBIC_METER,
        state_class=SensorStateClass.MEASUREMENT,
        value=lambda data: data.get("co"),
    ),
    AirQEntityDescription(
        key="co2",
        name="CO2",
        device_class=SensorDeviceClass.CO2,
        native_unit_of_measurement=CONCENTRATION_PARTS_PER_MILLION,
        state_class=SensorStateClass.MEASUREMENT,
        value=lambda data: data.get("co2"),
    ),
    AirQEntityDescription(
        key="dew_point",
        name="Dew point",
        native_unit_of_measurement=TEMP_CELSIUS,
        state_class=SensorStateClass.MEASUREMENT,
        value=lambda data: data.get("dewpt"),
        icon="mdi:water-thermometer",
    ),
    AirQEntityDescription(
        key="ethanol",
        name="Ethanol",
        native_unit_of_measurement=CONCENTRATION_MICROGRAMS_PER_CUBIC_METER,
        state_class=SensorStateClass.MEASUREMENT,
        value=lambda data: data.get("ethanol"),
    ),
    AirQEntityDescription(
        key="formaldehyde",
        name="Formaldehyde",
        native_unit_of_measurement=CONCENTRATION_MICROGRAMS_PER_CUBIC_METER,
        state_class=SensorStateClass.MEASUREMENT,
        value=lambda data: data.get("ch2o_M10"),
    ),
    AirQEntityDescription(
        key="h2s",
        name="H2S",
        native_unit_of_measurement=CONCENTRATION_MICROGRAMS_PER_CUBIC_METER,
        state_class=SensorStateClass.MEASUREMENT,
        value=lambda data: data.get("h2s"),
    ),
    AirQEntityDescription(
        key="health",
        name="Health Index",
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        icon="mdi:heart-pulse",
        value=lambda data: data.get("health", 0.0) / 10.0,
    ),
    AirQEntityDescription(
        key="humidity",
        name="Humidity",
        device_class=SensorDeviceClass.HUMIDITY,
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        value=lambda data: data.get("humidity"),
    ),
    AirQEntityDescription(
        key="humidity_abs",
        name="Absolute humidity",
        native_unit_of_measurement=CONCENTRATION_GRAMS_PER_CUBIC_METER,
        state_class=SensorStateClass.MEASUREMENT,
        value=lambda data: data.get("humidity_abs"),
        icon="mdi:water",
    ),
    AirQEntityDescription(
        key="hydrogen",
        name="Hydrogen",
        native_unit_of_measurement=CONCENTRATION_MICROGRAMS_PER_CUBIC_METER,
        state_class=SensorStateClass.MEASUREMENT,
        value=lambda data: data.get("h2_M1000"),
    ),
    AirQEntityDescription(
        key="methane",
        name="Methane",
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        value=lambda data: data.get("ch4_MIPEX"),
    ),
    AirQEntityDescription(
        key="n2o",
        name="N2O",
        device_class=SensorDeviceClass.NITROUS_OXIDE,
        native_unit_of_measurement=CONCENTRATION_MICROGRAMS_PER_CUBIC_METER,
        state_class=SensorStateClass.MEASUREMENT,
        value=lambda data: data.get("n2o"),
    ),
    AirQEntityDescription(
        key="no",
        name="NO",
        device_class=SensorDeviceClass.NITROGEN_MONOXIDE,
        native_unit_of_measurement=CONCENTRATION_MICROGRAMS_PER_CUBIC_METER,
        state_class=SensorStateClass.MEASUREMENT,
        value=lambda data: data.get("no_M250"),
    ),
    AirQEntityDescription(
        key="no2",
        name="NO2",
        device_class=SensorDeviceClass.NITROGEN_DIOXIDE,
        native_unit_of_measurement=CONCENTRATION_MICROGRAMS_PER_CUBIC_METER,
        state_class=SensorStateClass.MEASUREMENT,
        value=lambda data: data.get("no2"),
    ),
    AirQEntityDescription(
        key="o3",
        name="Ozone",
        device_class=SensorDeviceClass.OZONE,
        native_unit_of_measurement=CONCENTRATION_MICROGRAMS_PER_CUBIC_METER,
        state_class=SensorStateClass.MEASUREMENT,
        value=lambda data: data.get("o3"),
    ),
    AirQEntityDescription(
        key="oxygen",
        name="Oxygen",
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        value=lambda data: data.get("oxygen"),
        icon="mdi:leaf",
    ),
    AirQEntityDescription(
        key="performance",
        name="Performance Index",
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        icon="mdi:head-check",
        value=lambda data: data.get("performance", 0.0) / 10.0,
    ),
    AirQEntityDescription(
        key="pm1",
        name="PM1",
        device_class=SensorDeviceClass.PM1,
        native_unit_of_measurement=CONCENTRATION_MICROGRAMS_PER_CUBIC_METER,
        state_class=SensorStateClass.MEASUREMENT,
        value=lambda data: data.get("pm1"),
        icon="mdi:dots-hexagon",
    ),
    AirQEntityDescription(
        key="pm2_5",
        name="PM2.5",
        device_class=SensorDeviceClass.PM25,
        native_unit_of_measurement=CONCENTRATION_MICROGRAMS_PER_CUBIC_METER,
        state_class=SensorStateClass.MEASUREMENT,
        value=lambda data: data.get("pm2_5"),
        icon="mdi:dots-hexagon",
    ),
    AirQEntityDescription(
        key="pm10",
        name="PM10",
        device_class=SensorDeviceClass.PM10,
        native_unit_of_measurement=CONCENTRATION_MICROGRAMS_PER_CUBIC_METER,
        state_class=SensorStateClass.MEASUREMENT,
        value=lambda data: data.get("pm10"),
        icon="mdi:dots-hexagon",
    ),
    AirQEntityDescription(
        key="pressure",
        name="Pressure",
        device_class=SensorDeviceClass.PRESSURE,
        native_unit_of_measurement=PRESSURE_HPA,
        state_class=SensorStateClass.MEASUREMENT,
        value=lambda data: data.get("pressure"),
    ),
    AirQEntityDescription(
        key="pressure_rel",
        name="Relative pressure",
        native_unit_of_measurement=PRESSURE_HPA,
        state_class=SensorStateClass.MEASUREMENT,
        value=lambda data: data.get("pressure_rel"),
        icon="mdi:gauge",
    ),
    AirQEntityDescription(
        key="propane",
        name="Propane",
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        value=lambda data: data.get("c3h8_MIPEX"),
    ),
    AirQEntityDescription(
        key="so2",
        name="SO2",
        device_class=SensorDeviceClass.SULPHUR_DIOXIDE,
        native_unit_of_measurement=CONCENTRATION_MICROGRAMS_PER_CUBIC_METER,
        state_class=SensorStateClass.MEASUREMENT,
        value=lambda data: data.get("so2"),
    ),
    AirQEntityDescription(
        key="sound",
        name="Noise",
        native_unit_of_measurement=SOUND_PRESSURE_WEIGHTED_DBA,
        state_class=SensorStateClass.MEASUREMENT,
        value=lambda data: data.get("sound"),
        icon="mdi:ear-hearing",
    ),
    AirQEntityDescription(
        key="sound_max",
        name="Noise (Maximum)",
        native_unit_of_measurement=SOUND_PRESSURE_WEIGHTED_DBA,
        state_class=SensorStateClass.MEASUREMENT,
        value=lambda data: data.get("sound_max"),
        icon="mdi:ear-hearing",
    ),
    AirQEntityDescription(
        key="radon",
        name="Radon",
        native_unit_of_measurement=ACTIVITY_BECQUEREL_PER_CUBIC_METER,
        state_class=SensorStateClass.MEASUREMENT,
        value=lambda data: data.get("radon"),
        icon="mdi:radioactive",
    ),
    AirQEntityDescription(
        key="temperature",
        name="Temperature",
        device_class=SensorDeviceClass.TEMPERATURE,
        native_unit_of_measurement=TEMP_CELSIUS,
        state_class=SensorStateClass.MEASUREMENT,
        value=lambda data: data.get("temperature"),
    ),
    AirQEntityDescription(
        key="tvoc",
        name="VOC",
        device_class=SensorDeviceClass.VOLATILE_ORGANIC_COMPOUNDS,
        native_unit_of_measurement=CONCENTRATION_PARTS_PER_BILLION,
        state_class=SensorStateClass.MEASUREMENT,
        value=lambda data: data.get("tvoc"),
    ),
    AirQEntityDescription(
        key="tvoc_industrial",
        name="VOC (Industrial)",
        device_class=SensorDeviceClass.VOLATILE_ORGANIC_COMPOUNDS,
        native_unit_of_measurement=CONCENTRATION_PARTS_PER_BILLION,
        state_class=SensorStateClass.MEASUREMENT,
        value=lambda data: data.get("tvoc_ionsc"),
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

    # Filter out non-sensor keys
    available_sensors = [
        description for description in SENSOR_TYPES if description.key in available_keys
    ]
    _LOGGER.debug(
        "Identified %d available sensors: %s",
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
        description: AirQEntityDescription,
    ) -> None:
        """Initialize a single sensor."""
        super().__init__(coordinator)
        self.entity_description: AirQEntityDescription = description

        self._attr_device_info = coordinator.device_info
        self._attr_name = description.name
        self._attr_unique_id = f"{coordinator.device_id}_{description.key}"
        self._attr_native_value = description.value(coordinator.data)

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        self._attr_native_value = self.entity_description.value(self.coordinator.data)
        self.async_write_ha_state()
