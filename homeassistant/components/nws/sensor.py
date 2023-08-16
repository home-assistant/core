"""Sensors for National Weather Service (NWS)."""
from __future__ import annotations

from dataclasses import dataclass
from types import MappingProxyType
from typing import Any

<<<<<<< HEAD
=======
from pynws import SimpleNWS

>>>>>>> dde6ce6a996 (Add unit tests)
from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
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
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.util.dt import utcnow
from homeassistant.util.unit_conversion import (
    DistanceConverter,
    PressureConverter,
    SpeedConverter,
)
from homeassistant.util.unit_system import US_CUSTOMARY_SYSTEM

<<<<<<< HEAD
from . import NWSData, NwsDataUpdateCoordinator, base_unique_id, device_info
from .const import ATTRIBUTION, CONF_STATION, DOMAIN, OBSERVATION_VALID_TIME
=======
from . import NwsDataUpdateCoordinator, base_unique_id, device_info
from .const import (
    ATTRIBUTION,
    CONF_STATION,
    COORDINATOR_OBSERVATION,
    DOMAIN,
    NWS_DATA,
    OBSERVATION_VALID_TIME,
)
>>>>>>> dde6ce6a996 (Add unit tests)

PARALLEL_UPDATES = 0


@dataclass
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
)


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up the NWS weather platform."""
<<<<<<< HEAD
    nws_data: NWSData = hass.data[DOMAIN][entry.entry_id]
=======
    hass_data = hass.data[DOMAIN][entry.entry_id]
>>>>>>> dde6ce6a996 (Add unit tests)
    station = entry.data[CONF_STATION]

    async_add_entities(
        NWSSensor(
            hass=hass,
            entry_data=entry.data,
<<<<<<< HEAD
            nws_data=nws_data,
=======
            hass_data=hass_data,
>>>>>>> dde6ce6a996 (Add unit tests)
            description=description,
            station=station,
        )
        for description in SENSOR_TYPES
    )


class NWSSensor(CoordinatorEntity[NwsDataUpdateCoordinator], SensorEntity):
    """An NWS Sensor Entity."""

    entity_description: NWSSensorEntityDescription
    _attr_attribution = ATTRIBUTION

    def __init__(
        self,
        hass: HomeAssistant,
        entry_data: MappingProxyType[str, Any],
<<<<<<< HEAD
        nws_data: NWSData,
=======
        hass_data: dict[str, Any],
>>>>>>> dde6ce6a996 (Add unit tests)
        description: NWSSensorEntityDescription,
        station: str,
    ) -> None:
        """Initialise the platform with a data instance."""
<<<<<<< HEAD
        super().__init__(nws_data.coordinator_observation)
        self._nws = nws_data.api
=======
        super().__init__(hass_data[COORDINATOR_OBSERVATION])
        self._nws: SimpleNWS = hass_data[NWS_DATA]
>>>>>>> dde6ce6a996 (Add unit tests)
        self._latitude = entry_data[CONF_LATITUDE]
        self._longitude = entry_data[CONF_LONGITUDE]
        self.entity_description = description

        self._attr_name = f"{station} {description.name}"
        if hass.config.units is US_CUSTOMARY_SYSTEM:
            self._attr_native_unit_of_measurement = description.unit_convert

    @property
    def native_value(self) -> float | None:
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
        return value

    @property
    def unique_id(self) -> str:
        """Return a unique_id for this entity."""
        return f"{base_unique_id(self._latitude, self._longitude)}_{self.entity_description.key}"

    @property
    def available(self) -> bool:
        """Return if state is available."""
        if self.coordinator.last_update_success_time:
            last_success_time = (
                utcnow() - self.coordinator.last_update_success_time
                < OBSERVATION_VALID_TIME
            )
        else:
            last_success_time = False
        return self.coordinator.last_update_success or last_success_time

    @property
    def entity_registry_enabled_default(self) -> bool:
        """Return if the entity should be enabled when first added to the entity registry."""
        return False

    @property
    def device_info(self) -> DeviceInfo:
        """Return device info."""
        return device_info(self._latitude, self._longitude)
