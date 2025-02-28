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
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import AirQConfigEntry, AirQCoordinator
from .const import (
    ACTIVITY_BECQUEREL_PER_CUBIC_METER,
    CONCENTRATION_GRAMS_PER_CUBIC_METER,
)

_LOGGER = logging.getLogger(__name__)


@dataclass(frozen=True, kw_only=True)
class AirQSensorEntityDescription(SensorEntityDescription):
    """Describes AirQ sensor entity."""

    value: Callable[[dict], float | int | None]


# Keys must match those in the data dictionary
SENSOR_TYPES: list[AirQSensorEntityDescription] = [
    AirQSensorEntityDescription(
        key="c2h4o",
        translation_key="acetaldehyde",
        native_unit_of_measurement=CONCENTRATION_MICROGRAMS_PER_CUBIC_METER,
        state_class=SensorStateClass.MEASUREMENT,
        value=lambda data: data.get("c2h4o"),
    ),
    AirQSensorEntityDescription(
        key="nh3_MR100",
        translation_key="ammonia",
        native_unit_of_measurement=CONCENTRATION_MICROGRAMS_PER_CUBIC_METER,
        state_class=SensorStateClass.MEASUREMENT,
        value=lambda data: data.get("nh3_MR100"),
    ),
    AirQSensorEntityDescription(
        key="ash3",
        translation_key="arsine",
        native_unit_of_measurement=CONCENTRATION_MICROGRAMS_PER_CUBIC_METER,
        state_class=SensorStateClass.MEASUREMENT,
        value=lambda data: data.get("ash3"),
    ),
    AirQSensorEntityDescription(
        key="br2",
        translation_key="bromine",
        native_unit_of_measurement=CONCENTRATION_MICROGRAMS_PER_CUBIC_METER,
        state_class=SensorStateClass.MEASUREMENT,
        value=lambda data: data.get("br2"),
    ),
    AirQSensorEntityDescription(
        key="ch4s",
        translation_key="methanethiol",
        native_unit_of_measurement=CONCENTRATION_MICROGRAMS_PER_CUBIC_METER,
        state_class=SensorStateClass.MEASUREMENT,
        value=lambda data: data.get("ch4s"),
    ),
    AirQSensorEntityDescription(
        key="cl2_M20",
        translation_key="chlorine",
        native_unit_of_measurement=CONCENTRATION_MICROGRAMS_PER_CUBIC_METER,
        state_class=SensorStateClass.MEASUREMENT,
        value=lambda data: data.get("cl2_M20"),
    ),
    AirQSensorEntityDescription(
        key="clo2",
        translation_key="chlorine_dioxide",
        native_unit_of_measurement=CONCENTRATION_MICROGRAMS_PER_CUBIC_METER,
        state_class=SensorStateClass.MEASUREMENT,
        value=lambda data: data.get("clo2"),
    ),
    AirQSensorEntityDescription(
        key="co",
        translation_key="carbon_monoxide",
        native_unit_of_measurement=CONCENTRATION_MILLIGRAMS_PER_CUBIC_METER,
        state_class=SensorStateClass.MEASUREMENT,
        value=lambda data: data.get("co"),
    ),
    AirQSensorEntityDescription(
        key="co2",
        device_class=SensorDeviceClass.CO2,
        native_unit_of_measurement=CONCENTRATION_PARTS_PER_MILLION,
        state_class=SensorStateClass.MEASUREMENT,
        value=lambda data: data.get("co2"),
    ),
    AirQSensorEntityDescription(
        key="cs2",
        translation_key="carbon_disulfide",
        native_unit_of_measurement=CONCENTRATION_MICROGRAMS_PER_CUBIC_METER,
        state_class=SensorStateClass.MEASUREMENT,
        value=lambda data: data.get("cs2"),
    ),
    AirQSensorEntityDescription(
        key="dewpt",
        translation_key="dew_point",
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        state_class=SensorStateClass.MEASUREMENT,
        value=lambda data: data.get("dewpt"),
        device_class=SensorDeviceClass.TEMPERATURE,
    ),
    AirQSensorEntityDescription(
        key="ethanol",
        translation_key="ethanol",
        native_unit_of_measurement=CONCENTRATION_MICROGRAMS_PER_CUBIC_METER,
        state_class=SensorStateClass.MEASUREMENT,
        value=lambda data: data.get("ethanol"),
    ),
    AirQSensorEntityDescription(
        key="c2h4",
        translation_key="ethylene",
        native_unit_of_measurement=CONCENTRATION_MICROGRAMS_PER_CUBIC_METER,
        state_class=SensorStateClass.MEASUREMENT,
        value=lambda data: data.get("c2h4"),
    ),
    AirQSensorEntityDescription(
        key="ch2o_M10",
        translation_key="formaldehyde",
        native_unit_of_measurement=CONCENTRATION_MICROGRAMS_PER_CUBIC_METER,
        state_class=SensorStateClass.MEASUREMENT,
        value=lambda data: data.get("ch2o_M10"),
    ),
    AirQSensorEntityDescription(
        key="f2",
        translation_key="fluorine",
        native_unit_of_measurement=CONCENTRATION_MICROGRAMS_PER_CUBIC_METER,
        state_class=SensorStateClass.MEASUREMENT,
        value=lambda data: data.get("f2"),
    ),
    AirQSensorEntityDescription(
        key="h2s",
        translation_key="hydrogen_sulfide",
        native_unit_of_measurement=CONCENTRATION_MICROGRAMS_PER_CUBIC_METER,
        state_class=SensorStateClass.MEASUREMENT,
        value=lambda data: data.get("h2s"),
    ),
    AirQSensorEntityDescription(
        key="hcl",
        translation_key="hydrochloric_acid",
        native_unit_of_measurement=CONCENTRATION_MICROGRAMS_PER_CUBIC_METER,
        state_class=SensorStateClass.MEASUREMENT,
        value=lambda data: data.get("hcl"),
    ),
    AirQSensorEntityDescription(
        key="hcn",
        translation_key="hydrogen_cyanide",
        native_unit_of_measurement=CONCENTRATION_MICROGRAMS_PER_CUBIC_METER,
        state_class=SensorStateClass.MEASUREMENT,
        value=lambda data: data.get("hcn"),
    ),
    AirQSensorEntityDescription(
        key="hf",
        translation_key="hydrogen_fluoride",
        native_unit_of_measurement=CONCENTRATION_MICROGRAMS_PER_CUBIC_METER,
        state_class=SensorStateClass.MEASUREMENT,
        value=lambda data: data.get("hf"),
    ),
    AirQSensorEntityDescription(
        key="health",
        translation_key="health_index",
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        value=lambda data: data.get("health", 0.0) / 10.0,
    ),
    AirQSensorEntityDescription(
        key="humidity",
        device_class=SensorDeviceClass.HUMIDITY,
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        value=lambda data: data.get("humidity"),
    ),
    AirQSensorEntityDescription(
        key="humidity_abs",
        translation_key="absolute_humidity",
        native_unit_of_measurement=CONCENTRATION_GRAMS_PER_CUBIC_METER,
        state_class=SensorStateClass.MEASUREMENT,
        value=lambda data: data.get("humidity_abs"),
    ),
    AirQSensorEntityDescription(
        key="h2_M1000",
        translation_key="hydrogen",
        native_unit_of_measurement=CONCENTRATION_MICROGRAMS_PER_CUBIC_METER,
        state_class=SensorStateClass.MEASUREMENT,
        value=lambda data: data.get("h2_M1000"),
    ),
    AirQSensorEntityDescription(
        key="h2o2",
        translation_key="hydrogen_peroxide",
        native_unit_of_measurement=CONCENTRATION_MICROGRAMS_PER_CUBIC_METER,
        state_class=SensorStateClass.MEASUREMENT,
        value=lambda data: data.get("h2o2"),
    ),
    AirQSensorEntityDescription(
        key="ch4_MIPEX",
        translation_key="methane",
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        value=lambda data: data.get("ch4_MIPEX"),
    ),
    AirQSensorEntityDescription(
        key="n2o",
        device_class=SensorDeviceClass.NITROUS_OXIDE,
        native_unit_of_measurement=CONCENTRATION_MICROGRAMS_PER_CUBIC_METER,
        state_class=SensorStateClass.MEASUREMENT,
        value=lambda data: data.get("n2o"),
    ),
    AirQSensorEntityDescription(
        key="no_M250",
        device_class=SensorDeviceClass.NITROGEN_MONOXIDE,
        native_unit_of_measurement=CONCENTRATION_MICROGRAMS_PER_CUBIC_METER,
        state_class=SensorStateClass.MEASUREMENT,
        value=lambda data: data.get("no_M250"),
    ),
    AirQSensorEntityDescription(
        key="no2",
        device_class=SensorDeviceClass.NITROGEN_DIOXIDE,
        native_unit_of_measurement=CONCENTRATION_MICROGRAMS_PER_CUBIC_METER,
        state_class=SensorStateClass.MEASUREMENT,
        value=lambda data: data.get("no2"),
    ),
    AirQSensorEntityDescription(
        key="acid_M100",
        translation_key="organic_acid",
        native_unit_of_measurement=CONCENTRATION_PARTS_PER_BILLION,
        state_class=SensorStateClass.MEASUREMENT,
        value=lambda data: data.get("acid_M100"),
    ),
    AirQSensorEntityDescription(
        key="oxygen",
        translation_key="oxygen",
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        value=lambda data: data.get("oxygen"),
    ),
    AirQSensorEntityDescription(
        key="o3",
        device_class=SensorDeviceClass.OZONE,
        native_unit_of_measurement=CONCENTRATION_MICROGRAMS_PER_CUBIC_METER,
        state_class=SensorStateClass.MEASUREMENT,
        value=lambda data: data.get("o3"),
    ),
    AirQSensorEntityDescription(
        key="performance",
        translation_key="performance_index",
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        value=lambda data: data.get("performance", 0.0) / 10.0,
    ),
    AirQSensorEntityDescription(
        key="ph3",
        translation_key="hydrogen_phosphide",
        native_unit_of_measurement=CONCENTRATION_MICROGRAMS_PER_CUBIC_METER,
        state_class=SensorStateClass.MEASUREMENT,
        value=lambda data: data.get("ph3"),
    ),
    AirQSensorEntityDescription(
        key="pm1",
        device_class=SensorDeviceClass.PM1,
        native_unit_of_measurement=CONCENTRATION_MICROGRAMS_PER_CUBIC_METER,
        state_class=SensorStateClass.MEASUREMENT,
        value=lambda data: data.get("pm1"),
    ),
    AirQSensorEntityDescription(
        key="pm2_5",
        device_class=SensorDeviceClass.PM25,
        native_unit_of_measurement=CONCENTRATION_MICROGRAMS_PER_CUBIC_METER,
        state_class=SensorStateClass.MEASUREMENT,
        value=lambda data: data.get("pm2_5"),
    ),
    AirQSensorEntityDescription(
        key="pm10",
        device_class=SensorDeviceClass.PM10,
        native_unit_of_measurement=CONCENTRATION_MICROGRAMS_PER_CUBIC_METER,
        state_class=SensorStateClass.MEASUREMENT,
        value=lambda data: data.get("pm10"),
    ),
    AirQSensorEntityDescription(
        key="pressure",
        device_class=SensorDeviceClass.PRESSURE,
        native_unit_of_measurement=UnitOfPressure.HPA,
        state_class=SensorStateClass.MEASUREMENT,
        value=lambda data: data.get("pressure"),
    ),
    AirQSensorEntityDescription(
        key="pressure_rel",
        translation_key="relative_pressure",
        native_unit_of_measurement=UnitOfPressure.HPA,
        state_class=SensorStateClass.MEASUREMENT,
        value=lambda data: data.get("pressure_rel"),
        device_class=SensorDeviceClass.PRESSURE,
    ),
    AirQSensorEntityDescription(
        key="c3h8_MIPEX",
        translation_key="propane",
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        value=lambda data: data.get("c3h8_MIPEX"),
    ),
    AirQSensorEntityDescription(
        key="refigerant",
        translation_key="refigerant",
        native_unit_of_measurement=CONCENTRATION_MICROGRAMS_PER_CUBIC_METER,
        state_class=SensorStateClass.MEASUREMENT,
        value=lambda data: data.get("refigerant"),
    ),
    AirQSensorEntityDescription(
        key="sih4",
        translation_key="silicon_hydride",
        native_unit_of_measurement=CONCENTRATION_MICROGRAMS_PER_CUBIC_METER,
        state_class=SensorStateClass.MEASUREMENT,
        value=lambda data: data.get("sih4"),
    ),
    AirQSensorEntityDescription(
        key="so2",
        device_class=SensorDeviceClass.SULPHUR_DIOXIDE,
        native_unit_of_measurement=CONCENTRATION_MICROGRAMS_PER_CUBIC_METER,
        state_class=SensorStateClass.MEASUREMENT,
        value=lambda data: data.get("so2"),
    ),
    AirQSensorEntityDescription(
        key="sound",
        translation_key="noise",
        native_unit_of_measurement=UnitOfSoundPressure.WEIGHTED_DECIBEL_A,
        state_class=SensorStateClass.MEASUREMENT,
        value=lambda data: data.get("sound"),
        device_class=SensorDeviceClass.SOUND_PRESSURE,
    ),
    AirQSensorEntityDescription(
        key="sound_max",
        translation_key="maximum_noise",
        native_unit_of_measurement=UnitOfSoundPressure.WEIGHTED_DECIBEL_A,
        state_class=SensorStateClass.MEASUREMENT,
        value=lambda data: data.get("sound_max"),
        device_class=SensorDeviceClass.SOUND_PRESSURE,
    ),
    AirQSensorEntityDescription(
        key="radon",
        translation_key="radon",
        native_unit_of_measurement=ACTIVITY_BECQUEREL_PER_CUBIC_METER,
        state_class=SensorStateClass.MEASUREMENT,
        value=lambda data: data.get("radon"),
    ),
    AirQSensorEntityDescription(
        key="temperature",
        device_class=SensorDeviceClass.TEMPERATURE,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        state_class=SensorStateClass.MEASUREMENT,
        value=lambda data: data.get("temperature"),
    ),
    AirQSensorEntityDescription(
        key="tvoc",
        device_class=SensorDeviceClass.VOLATILE_ORGANIC_COMPOUNDS_PARTS,
        native_unit_of_measurement=CONCENTRATION_PARTS_PER_BILLION,
        state_class=SensorStateClass.MEASUREMENT,
        value=lambda data: data.get("tvoc"),
    ),
    AirQSensorEntityDescription(
        key="tvoc_ionsc",
        translation_key="industrial_volatile_organic_compounds",
        device_class=SensorDeviceClass.VOLATILE_ORGANIC_COMPOUNDS_PARTS,
        native_unit_of_measurement=CONCENTRATION_PARTS_PER_BILLION,
        state_class=SensorStateClass.MEASUREMENT,
        value=lambda data: data.get("tvoc_ionsc"),
    ),
    AirQSensorEntityDescription(
        key="virus",
        translation_key="virus_index",
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        value=lambda data: data.get("virus", 0.0),
    ),
]


async def async_setup_entry(
    hass: HomeAssistant,
    entry: AirQConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up sensor entities based on a config entry."""

    coordinator = entry.runtime_data

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
        description: AirQSensorEntityDescription,
    ) -> None:
        """Initialize a single sensor."""
        super().__init__(coordinator)
        self.entity_description: AirQSensorEntityDescription = description

        self._attr_device_info = coordinator.device_info
        self._attr_unique_id = f"{coordinator.device_id}_{description.key}"
        self._attr_native_value = description.value(coordinator.data)

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        self._attr_native_value = self.entity_description.value(self.coordinator.data)
        self.async_write_ha_state()
