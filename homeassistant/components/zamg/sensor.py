"""Sensor for zamg the Austrian "Zentralanstalt für Meteorologie und Geodynamik" integration."""
from __future__ import annotations

import csv
from dataclasses import dataclass
from datetime import datetime, timedelta
import gzip
import json
import logging
import os
from typing import Union

import requests
import voluptuous as vol

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
    __version__,
)
from homeassistant.core import HomeAssistant
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.device_registry import DeviceEntryType
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.util import Throttle, dt as dt_util

from .const import (
    ATTR_STATION,
    ATTR_UPDATED,
    ATTRIBUTION,
    CONF_STATION_ID,
    DEFAULT_NAME,
    DOMAIN,
    MANUFACTURER_URL,
    MIN_TIME_BETWEEN_UPDATES,
    VIENNA_TIME_ZONE,
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
    # The following probably not useful for general consumption,
    # but we need them to fill in internal attributes
    ZamgSensorEntityDescription(
        key="station_name",
        name="Station Name",
        col_heading="Name",
        dtype=str,
    ),
    ZamgSensorEntityDescription(
        key="station_elevation",
        name="Station Elevation",
        native_unit_of_measurement=LENGTH_METERS,
        col_heading=f"Höhe {LENGTH_METERS}",
        dtype=int,
    ),
    ZamgSensorEntityDescription(
        key="update_date",
        name="Update Date",
        col_heading="Datum",
        dtype=str,
    ),
    ZamgSensorEntityDescription(
        key="update_time",
        name="Update Time",
        col_heading="Zeit",
        dtype=str,
    ),
    ZamgSensorEntityDescription(
        key="station_id",
        name="Station id",
        col_heading="Station",
        dtype=str,
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

    station_id = config.get(CONF_STATION_ID) or closest_station(
        latitude, longitude, hass.config.config_dir
    )
    if station_id not in _get_ogd_stations():
        _LOGGER.error(
            "Configured ZAMG %s (%s) is not a known station",
            CONF_STATION_ID,
            station_id,
        )
        return

    probe = ZamgData(station_id=station_id)
    try:
        probe.update()
    except (ValueError, TypeError) as err:
        _LOGGER.error("Sensor: Received error from ZAMG: %s", err)
        return

    monitored_conditions = config[CONF_MONITORED_CONDITIONS]
    add_entities(
        [
            ZamgSensor(probe, name, description)
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
    if coordinator.config_entry is None:
        coordinator.config_entry = entry

    async_add_entities(
        [
            ZamgSensor(coordinator, entry.title, description)
            for description in SENSOR_TYPES
        ],
        False,
    )


class ZamgSensor(CoordinatorEntity, SensorEntity):
    """Implementation of a ZAMG sensor."""

    _attr_attribution = ATTRIBUTION
    entity_description: ZamgSensorEntityDescription

    def __init__(self, coordinator, name, description: ZamgSensorEntityDescription):
        """Initialize the sensor."""
        super().__init__(coordinator)
        self.entity_description = description
        self.coordinator = coordinator
        self._attr_name = f"{name} {description.name}"
        self._attr_unique_id = (
            f"{self.coordinator.data.get('station_id')}_{description.key}"
        )

    @property
    def device_info(self):
        """Return the device info."""
        return DeviceInfo(
            entry_type=DeviceEntryType.SERVICE,
            identifiers={(DOMAIN, self.platform.config_entry.unique_id)},
            manufacturer=DOMAIN,
            configuration_url=MANUFACTURER_URL,
            name=self.coordinator.name,
        )

    @property
    def native_value(self):
        """Return the state of the sensor."""
        return self.coordinator.data.get(self.entity_description.key)

    @property
    def extra_state_attributes(self):
        """Return the state attributes."""
        update_time = datetime.strptime(
            f"{self.coordinator.data.get('update_date')} {self.coordinator.data.get('update_time')}",
            "%d-%m-%Y %H:%M",
        )
        return {
            ATTR_ATTRIBUTION: ATTRIBUTION,
            ATTR_STATION: self.coordinator.data.get("station_name"),
            CONF_STATION_ID: self.coordinator.config_entry.unique_id,
            ATTR_UPDATED: update_time.isoformat(),
        }

    def update(self) -> None:
        """Delegate update to probe."""
        self.coordinator.data.update()


@dataclass
class ZamgData:
    """The class for handling the data retrieval."""

    API_URL = "http://www.zamg.ac.at/ogd/"
    API_HEADERS = {"User-Agent": f"home-assistant.zamg/ {__version__}"}

    def __init__(self, station_id):
        """Initialize the probe."""
        self._station_id = station_id
        self.data = {}

    @property
    def last_update(self):
        """Return the timestamp of the most recent data."""
        date, time = self.data.get("update_date"), self.data.get("update_time")
        if date is not None and time is not None:
            return datetime.strptime(date + time, "%d-%m-%Y%H:%M").replace(
                tzinfo=VIENNA_TIME_ZONE
            )

    @property
    def station_id(self) -> str:
        """Return the station id."""
        return self._station_id

    @classmethod
    def current_observations(cls):
        """Fetch the latest CSV data."""
        try:
            response = requests.get(cls.API_URL, headers=cls.API_HEADERS, timeout=15)
            response.raise_for_status()
            response.encoding = "UTF8"
            return csv.DictReader(
                response.text.splitlines(), delimiter=";", quotechar='"'
            )
        except requests.exceptions.HTTPError:
            _LOGGER.error("While fetching data")

    @Throttle(MIN_TIME_BETWEEN_UPDATES)
    def update(self):
        """Get the latest data from ZAMG."""
        if self.last_update and (
            self.last_update + timedelta(hours=1)
            > datetime.utcnow().replace(tzinfo=dt_util.UTC)
        ):
            return  # Not time to update yet; data is only hourly

        for row in self.current_observations():
            if row.get("Station") == self._station_id:
                self.data = {
                    API_FIELDS[col_heading][0]: API_FIELDS[col_heading][1](
                        v.replace(",", ".")
                    )
                    for col_heading, v in row.items()
                    if col_heading in API_FIELDS and v
                }
                break
        else:
            raise ValueError(f"No weather data for station {self._station_id}")

    def get_data(self, variable):
        """Get the data."""
        return self.data.get(variable)


def _get_ogd_stations():
    """Return all stations in the OGD dataset."""
    return {r["Station"] for r in ZamgData.current_observations()}


def _get_zamg_stations():
    """Return {CONF_STATION: (lat, lon)} for all stations, for auto-config."""
    capital_stations = _get_ogd_stations()
    req = requests.get(
        "https://www.zamg.ac.at/cms/en/documents/climate/"
        "doc_metnetwork/zamg-observation-points",
        timeout=15,
    )
    stations = {}
    for row in csv.DictReader(req.text.splitlines(), delimiter=";", quotechar='"'):
        if row.get("synnr") in capital_stations:
            try:
                stations[row["synnr"]] = tuple(
                    float(row[coord].replace(",", "."))
                    for coord in ("breite_dezi", "länge_dezi")
                )
            except KeyError:
                _LOGGER.error("ZAMG schema changed again, cannot autodetect station")
    return stations


def zamg_stations(cache_dir):
    """Return {CONF_STATION: (lat, lon)} for all stations, for auto-config.

    Results from internet requests are cached as compressed json, making
    subsequent calls very much faster.
    """
    cache_file = os.path.join(cache_dir, ".zamg-stations.json.gz")
    if not os.path.isfile(cache_file):
        stations = _get_zamg_stations()
        with gzip.open(cache_file, "wt") as cache:
            json.dump(stations, cache, sort_keys=True)
        return stations
    with gzip.open(cache_file, "rt") as cache:
        return {k: tuple(v) for k, v in json.load(cache).items()}


def closest_station(lat, lon, cache_dir):
    """Return the ZONE_ID.WMO_ID of the closest station to our lat/lon."""
    if lat is None or lon is None or not os.path.isdir(cache_dir):
        return
    stations = zamg_stations(cache_dir)

    def comparable_dist(zamg_id):
        """Calculate the pseudo-distance from lat/lon."""
        station_lat, station_lon = stations[zamg_id]
        return (lat - station_lat) ** 2 + (lon - station_lon) ** 2

    return min(stations, key=comparable_dist)
