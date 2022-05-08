"""Sensor for zamg the Austrian "Zentralanstalt für Meteorologie und Geodynamik" integration."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Union

import voluptuous as vol
from zamg import ZamgData

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    AREA_SQUARE_METERS,
    CONF_LATITUDE,
    CONF_LONGITUDE,
    CONF_MONITORED_CONDITIONS,
    CONF_NAME,
    DEGREE,
    LENGTH_METERS,
    PERCENTAGE,
    PRESSURE_HPA,
    SPEED_KILOMETERS_PER_HOUR,
    TEMP_CELSIUS,
)
from homeassistant.core import HomeAssistant
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.device_registry import DeviceEntryType
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import (
    ATTR_STATION,
    ATTR_UPDATED,
    ATTRIBUTION,
    CONF_STATION_ID,
    DEFAULT_NAME,
    DOMAIN,
    LOGGER,
    MANUFACTURER_URL,
)

_LOGGER = logging.getLogger(__name__)

_DType = Union[type[int], type[float], type[str]]


@dataclass
class ZamgRequiredKeysMixin:
    """Mixin for required keys."""

    col_heading: str
    dtype: _DType


@dataclass
class ZamgSensorEntityDescription(SensorEntityDescription, ZamgRequiredKeysMixin):
    """Describes Zamg sensor entity."""


SENSOR_TYPES: tuple[ZamgSensorEntityDescription, ...] = (
    ZamgSensorEntityDescription(
        key="pressure",
        name="Pressure",
        native_unit_of_measurement=PRESSURE_HPA,
        device_class=SensorDeviceClass.PRESSURE,
        state_class=SensorStateClass.MEASUREMENT,
        col_heading="LDstat hPa",
        dtype=float,
    ),
    ZamgSensorEntityDescription(
        key="pressure_sealevel",
        name="Pressure at Sea Level",
        native_unit_of_measurement=PRESSURE_HPA,
        device_class=SensorDeviceClass.PRESSURE,
        state_class=SensorStateClass.MEASUREMENT,
        col_heading="LDred hPa",
        dtype=float,
    ),
    ZamgSensorEntityDescription(
        key="humidity",
        name="Humidity",
        native_unit_of_measurement=PERCENTAGE,
        device_class=SensorDeviceClass.HUMIDITY,
        state_class=SensorStateClass.MEASUREMENT,
        col_heading="RF %",
        dtype=int,
    ),
    ZamgSensorEntityDescription(
        key="wind_speed",
        name="Wind Speed",
        native_unit_of_measurement=SPEED_KILOMETERS_PER_HOUR,
        state_class=SensorStateClass.MEASUREMENT,
        col_heading=f"WG {SPEED_KILOMETERS_PER_HOUR}",
        dtype=float,
    ),
    ZamgSensorEntityDescription(
        key="wind_bearing",
        name="Wind Bearing",
        native_unit_of_measurement=DEGREE,
        state_class=SensorStateClass.MEASUREMENT,
        col_heading=f"WR {DEGREE}",
        dtype=int,
    ),
    ZamgSensorEntityDescription(
        key="wind_max_speed",
        name="Top Wind Speed",
        native_unit_of_measurement=SPEED_KILOMETERS_PER_HOUR,
        state_class=SensorStateClass.MEASUREMENT,
        col_heading=f"WSG {SPEED_KILOMETERS_PER_HOUR}",
        dtype=float,
    ),
    ZamgSensorEntityDescription(
        key="wind_max_bearing",
        name="Top Wind Bearing",
        native_unit_of_measurement=DEGREE,
        state_class=SensorStateClass.MEASUREMENT,
        col_heading=f"WSR {DEGREE}",
        dtype=int,
    ),
    ZamgSensorEntityDescription(
        key="sun_last_hour",
        name="Sun Last Hour",
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        col_heading=f"SO {PERCENTAGE}",
        dtype=int,
    ),
    ZamgSensorEntityDescription(
        key="temperature",
        name="Temperature",
        native_unit_of_measurement=TEMP_CELSIUS,
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        col_heading=f"T {TEMP_CELSIUS}",
        dtype=float,
    ),
    ZamgSensorEntityDescription(
        key="precipitation",
        name="Precipitation",
        native_unit_of_measurement=f"l/{AREA_SQUARE_METERS}",
        state_class=SensorStateClass.MEASUREMENT,
        col_heading=f"N l/{AREA_SQUARE_METERS}",
        dtype=float,
    ),
    ZamgSensorEntityDescription(
        key="dewpoint",
        name="Dew Point",
        native_unit_of_measurement=TEMP_CELSIUS,
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        col_heading=f"TP {TEMP_CELSIUS}",
        dtype=float,
    ),
    # The following is probably not useful for general
    ZamgSensorEntityDescription(
        key="station_name",
        name="Station Name",
        col_heading="Name",
        dtype=str,
        entity_registry_enabled_default=False,
    ),
    ZamgSensorEntityDescription(
        key="station_elevation",
        name="Station Elevation",
        native_unit_of_measurement=LENGTH_METERS,
        col_heading=f"Höhe {LENGTH_METERS}",
        dtype=int,
        entity_registry_enabled_default=False,
    ),
    ZamgSensorEntityDescription(
        key="update_date",
        name="Update Date",
        col_heading="Datum",
        dtype=str,
        entity_registry_enabled_default=False,
    ),
    ZamgSensorEntityDescription(
        key="update_time",
        name="Update Time",
        col_heading="Zeit",
        dtype=str,
        entity_registry_enabled_default=False,
    ),
)

SENSOR_KEYS: list[str] = [desc.key for desc in SENSOR_TYPES]

API_FIELDS: dict[str, tuple[str, _DType]] = {
    desc.col_heading: (desc.key, desc.dtype) for desc in SENSOR_TYPES
}

PLATFORM_SCHEMA = cv.PLATFORM_SCHEMA.extend(
    {
        vol.Required(CONF_MONITORED_CONDITIONS, default=["temperature"]): vol.All(
            cv.ensure_list, [vol.In(SENSOR_KEYS)]
        ),
        vol.Optional(CONF_STATION_ID): cv.string,
        vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
        vol.Inclusive(
            CONF_LATITUDE, "coordinates", "Latitude and longitude must exist together"
        ): cv.latitude,
        vol.Inclusive(
            CONF_LONGITUDE, "coordinates", "Latitude and longitude must exist together"
        ): cv.longitude,
    }
)


def setup_platform(
    hass: HomeAssistant,
    config: ConfigType,
    add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None,
) -> None:
    """Set up the ZAMG sensor platform."""
    name = config[CONF_NAME]
    latitude = config.get(CONF_LATITUDE, hass.config.latitude)
    longitude = config.get(CONF_LONGITUDE, hass.config.longitude)
    station_id = config.get(CONF_STATION_ID)

    probe = ZamgData(station_id)

    station_id = station_id or probe.closest_station(
        latitude, longitude, hass.config.config_dir
    )
    if station_id not in probe.zamg_stations():
        LOGGER.error(
            "Configured ZAMG %s (%s) is not a known station",
            CONF_STATION_ID,
            station_id,
        )
        return

    try:
        probe.update()
    except (ValueError, TypeError) as err:
        LOGGER.error("Sensor: Received error from ZAMG: %s", err)
        return

    monitored_conditions = config[CONF_MONITORED_CONDITIONS]
    add_entities(
        [
            ZamgSensor(probe, name, station_id, description)
            for description in SENSOR_TYPES
            if description.key in monitored_conditions
        ],
        True,
    )


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up the ZAMG sensor platform."""
    coordinator = hass.data[DOMAIN][entry.entry_id]

    async_add_entities(
        ZamgSensor(coordinator, entry.title, entry.data[CONF_STATION_ID], description)
        for description in SENSOR_TYPES
    )


class ZamgSensor(CoordinatorEntity, SensorEntity):
    """Implementation of a ZAMG sensor."""

    _attr_attribution = ATTRIBUTION
    entity_description: ZamgSensorEntityDescription

    def __init__(
        self, coordinator, name, station_id, description: ZamgSensorEntityDescription
    ):
        """Initialize the sensor."""
        super().__init__(coordinator)
        self.entity_description = description
        self._attr_name = f"{name} {description.name}"
        self._attr_unique_id = f"{station_id}_{description.key}"
        self.station_id = f"{station_id}"
        self._attr_device_info = DeviceInfo(
            entry_type=DeviceEntryType.SERVICE,
            identifiers={(DOMAIN, station_id)},
            manufacturer=ATTRIBUTION,
            configuration_url=MANUFACTURER_URL,
            name=coordinator.name,
        )

    @property
    def native_value(self):
        """Return the state of the sensor."""
        val = self.coordinator.data[self.station_id].get(
            self.entity_description.col_heading
        )
        try:
            if self.entity_description.dtype == float:
                return float(val.replace(",", "."))
            if self.entity_description.dtype == int:
                return int(val.replace(",", "."))
            return val
        except ValueError:
            return val

    @property
    def extra_state_attributes(self):
        """Return the state attributes."""
        update_time = self.coordinator.data.get("last_update", "")
        return {
            ATTR_ATTRIBUTION: ATTRIBUTION,
            ATTR_STATION: self.coordinator.data[self.station_id].get("Name"),
            CONF_STATION_ID: self.station_id,
            ATTR_UPDATED: update_time.isoformat(),
        }
