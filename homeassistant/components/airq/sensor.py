"""Definition of air-Q sensor platform."""
from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
import logging
from typing import Literal

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
    UnitOfPressure,
    UnitOfSoundPressure,
    UnitOfTemperature,
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
        key="nh3_MR100",
        name="Ammonia",
        native_unit_of_measurement=CONCENTRATION_MICROGRAMS_PER_CUBIC_METER,
        state_class=SensorStateClass.MEASUREMENT,
        value=lambda data: data.get("nh3_MR100"),
    ),
    AirQEntityDescription(
        key="cl2_M20",
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
        key="dewpt",
        name="Dew point",
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        state_class=SensorStateClass.MEASUREMENT,
        value=lambda data: data.get("dewpt"),
        device_class=SensorDeviceClass.TEMPERATURE,
    ),
    AirQEntityDescription(
        key="ethanol",
        name="Ethanol",
        native_unit_of_measurement=CONCENTRATION_MICROGRAMS_PER_CUBIC_METER,
        state_class=SensorStateClass.MEASUREMENT,
        value=lambda data: data.get("ethanol"),
    ),
    AirQEntityDescription(
        key="ch2o_M10",
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
        key="h2_M1000",
        name="Hydrogen",
        native_unit_of_measurement=CONCENTRATION_MICROGRAMS_PER_CUBIC_METER,
        state_class=SensorStateClass.MEASUREMENT,
        value=lambda data: data.get("h2_M1000"),
    ),
    AirQEntityDescription(
        key="ch4_MIPEX",
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
        key="no_M250",
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
        native_unit_of_measurement=UnitOfPressure.HPA,
        state_class=SensorStateClass.MEASUREMENT,
        value=lambda data: data.get("pressure"),
    ),
    AirQEntityDescription(
        key="pressure_rel",
        name="Relative pressure",
        native_unit_of_measurement=UnitOfPressure.HPA,
        state_class=SensorStateClass.MEASUREMENT,
        value=lambda data: data.get("pressure_rel"),
        device_class=SensorDeviceClass.PRESSURE,
    ),
    AirQEntityDescription(
        key="c3h8_MIPEX",
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
        native_unit_of_measurement=UnitOfSoundPressure.WEIGHTED_DECIBEL_A,
        state_class=SensorStateClass.MEASUREMENT,
        value=lambda data: data.get("sound"),
        device_class=SensorDeviceClass.SOUND_PRESSURE,
    ),
    AirQEntityDescription(
        key="sound_max",
        name="Noise (Maximum)",
        native_unit_of_measurement=UnitOfSoundPressure.WEIGHTED_DECIBEL_A,
        state_class=SensorStateClass.MEASUREMENT,
        value=lambda data: data.get("sound_max"),
        device_class=SensorDeviceClass.SOUND_PRESSURE,
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
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
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
        key="tvoc_ionsc",
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

    entities: list[AirQSensor] = []

    device_status: dict[str, str] | Literal["OK"] = coordinator.data["Status"]

    for description in SENSOR_TYPES:
        if description.key not in coordinator.data:
            if isinstance(
                device_status, dict
            ) and "sensor still in warm up phase" in device_status.get(
                description.key, "OK"
            ):
                # warming up sensors do not contribute keys to coordinator.data
                # but still must be added
                _LOGGER.debug("Following sensor is warming up: %s", description.key)
            else:
                continue
        entities.append(AirQSensor(coordinator, description))

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
        self._attr_unique_id = f"{coordinator.device_id}_{description.key}"
        self._attr_native_value = description.value(coordinator.data)

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        self._attr_native_value = self.entity_description.value(self.coordinator.data)
        self.async_write_ha_state()
