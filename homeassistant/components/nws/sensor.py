"""Sensors for National Weather Service (NWS)."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from types import MappingProxyType
from typing import Any

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import (
    CONF_LATITUDE,
    CONF_LONGITUDE,
    DEGREE,
    PERCENTAGE,
    UnitOfLength,
    UnitOfPressure,
    UnitOfSpeed,
    UnitOfTemperature,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import (
    CoordinatorEntity,
    TimestampDataUpdateCoordinator,
)
from homeassistant.util.dt import parse_datetime
from homeassistant.util.unit_conversion import (
    DistanceConverter,
    PressureConverter,
    SpeedConverter,
)
from homeassistant.util.unit_system import US_CUSTOMARY_SYSTEM

from . import NWSConfigEntry, NWSData, base_unique_id, device_info
from .const import ATTRIBUTION, CONF_STATION

PARALLEL_UPDATES = 0


@dataclass(frozen=True)
class NWSSensorEntityDescription(SensorEntityDescription):
    """Class describing NWSSensor entities."""

    unit_convert: str | None = None


SENSOR_TYPES: tuple[NWSSensorEntityDescription, ...] = (
    NWSSensorEntityDescription(
        key="dewpoint",
        name="Dew Point",
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        unit_convert=UnitOfTemperature.CELSIUS,
    ),
    NWSSensorEntityDescription(
        key="temperature",
        name="Temperature",
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        unit_convert=UnitOfTemperature.CELSIUS,
    ),
    NWSSensorEntityDescription(
        key="windChill",
        name="Wind Chill",
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        unit_convert=UnitOfTemperature.CELSIUS,
    ),
    NWSSensorEntityDescription(
        key="heatIndex",
        name="Heat Index",
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        unit_convert=UnitOfTemperature.CELSIUS,
    ),
    NWSSensorEntityDescription(
        key="relativeHumidity",
        name="Relative Humidity",
        device_class=SensorDeviceClass.HUMIDITY,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=PERCENTAGE,
        unit_convert=PERCENTAGE,
    ),
    NWSSensorEntityDescription(
        key="windSpeed",
        name="Wind Speed",
        device_class=SensorDeviceClass.WIND_SPEED,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfSpeed.KILOMETERS_PER_HOUR,
        unit_convert=UnitOfSpeed.MILES_PER_HOUR,
    ),
    NWSSensorEntityDescription(
        key="windGust",
        name="Wind Gust",
        device_class=SensorDeviceClass.WIND_SPEED,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfSpeed.KILOMETERS_PER_HOUR,
        unit_convert=UnitOfSpeed.MILES_PER_HOUR,
    ),
    # statistics currently doesn't handle circular statistics
    NWSSensorEntityDescription(
        key="windDirection",
        name="Wind Direction",
        icon="mdi:compass-rose",
        native_unit_of_measurement=DEGREE,
        unit_convert=DEGREE,
    ),
    NWSSensorEntityDescription(
        key="barometricPressure",
        name="Barometric Pressure",
        device_class=SensorDeviceClass.PRESSURE,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfPressure.PA,
        unit_convert=UnitOfPressure.INHG,
    ),
    NWSSensorEntityDescription(
        key="seaLevelPressure",
        name="Sea Level Pressure",
        device_class=SensorDeviceClass.PRESSURE,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfPressure.PA,
        unit_convert=UnitOfPressure.INHG,
    ),
    NWSSensorEntityDescription(
        key="visibility",
        name="Visibility",
        icon="mdi:eye",
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfLength.METERS,
        unit_convert=UnitOfLength.MILES,
    ),
    NWSSensorEntityDescription(
        key="timestamp",
        name="Latest Observation Time",
        device_class=SensorDeviceClass.TIMESTAMP,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant, entry: NWSConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up the NWS weather platform."""
    nws_data = entry.runtime_data
    station = entry.data[CONF_STATION]

    async_add_entities(
        NWSSensor(
            hass=hass,
            entry_data=entry.data,
            nws_data=nws_data,
            description=description,
            station=station,
        )
        for description in SENSOR_TYPES
    )


class NWSSensor(CoordinatorEntity[TimestampDataUpdateCoordinator[None]], SensorEntity):
    """An NWS Sensor Entity."""

    entity_description: NWSSensorEntityDescription
    _attr_attribution = ATTRIBUTION
    _attr_entity_registry_enabled_default = False

    def __init__(
        self,
        hass: HomeAssistant,
        entry_data: MappingProxyType[str, Any],
        nws_data: NWSData,
        description: NWSSensorEntityDescription,
        station: str,
    ) -> None:
        """Initialise the platform with a data instance."""
        super().__init__(nws_data.coordinator_observation)
        self._nws = nws_data.api
        latitude = entry_data[CONF_LATITUDE]
        longitude = entry_data[CONF_LONGITUDE]
        self.entity_description = description

        self._attr_name = f"{station} {description.name}"
        if hass.config.units is US_CUSTOMARY_SYSTEM:
            self._attr_native_unit_of_measurement = description.unit_convert
        self._attr_device_info = device_info(latitude, longitude)
        self._attr_unique_id = (
            f"{base_unique_id(latitude, longitude)}_{description.key}"
        )

    @property
    def native_value(self) -> float | datetime | None:
        """Return the state."""
        if (
            not (observation := self._nws.observation)
            or (value := observation.get(self.entity_description.key)) is None
        ):
            return None

        # Set alias to unit property -> prevent unnecessary hasattr calls
        unit_of_measurement = self.native_unit_of_measurement
        if unit_of_measurement == UnitOfSpeed.MILES_PER_HOUR:
            return round(
                SpeedConverter.convert(
                    value, UnitOfSpeed.KILOMETERS_PER_HOUR, UnitOfSpeed.MILES_PER_HOUR
                )
            )
        if unit_of_measurement == UnitOfLength.MILES:
            return round(
                DistanceConverter.convert(
                    value, UnitOfLength.METERS, UnitOfLength.MILES
                )
            )
        if unit_of_measurement == UnitOfPressure.INHG:
            return round(
                PressureConverter.convert(
                    value, UnitOfPressure.PA, UnitOfPressure.INHG
                ),
                2,
            )
        if unit_of_measurement == UnitOfTemperature.CELSIUS:
            return round(value, 1)
        if unit_of_measurement == PERCENTAGE:
            return round(value)
        if self.device_class == SensorDeviceClass.TIMESTAMP:
            return parse_datetime(value)
        return value
