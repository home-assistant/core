"""Sensor for the Austrian "Zentralanstalt für Meteorologie und Geodynamik"."""
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
)
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
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType
from homeassistant.util import Throttle, dt as dt_util

_LOGGER = logging.getLogger(__name__)

ATTR_STATION = "station"
ATTR_UPDATED = "updated"
ATTRIBUTION = "Data provided by ZAMG"

CONF_STATION_ID = "station_id"

DEFAULT_NAME = "zamg"

MIN_TIME_BETWEEN_UPDATES = timedelta(minutes=10)
VIENNA_TIME_ZONE = dt_util.get_time_zone("Europe/Vienna")

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
        col_heading="LDstat hPa",
        dtype=float,
    ),
    ZamgSensorEntityDescription(
        key="pressure_sealevel",
        name="Pressure at Sea Level",
        native_unit_of_measurement=PRESSURE_HPA,
        col_heading="LDred hPa",
        dtype=float,
    ),
    ZamgSensorEntityDescription(
        key="humidity",
        name="Humidity",
        native_unit_of_measurement=PERCENTAGE,
        col_heading="RF %",
        dtype=int,
    ),
    ZamgSensorEntityDescription(
        key="wind_speed",
        name="Wind Speed",
        native_unit_of_measurement=SPEED_KILOMETERS_PER_HOUR,
        col_heading=f"WG {SPEED_KILOMETERS_PER_HOUR}",
        dtype=float,
    ),
    ZamgSensorEntityDescription(
        key="wind_bearing",
        name="Wind Bearing",
        native_unit_of_measurement=DEGREE,
        col_heading=f"WR {DEGREE}",
        dtype=int,
    ),
    ZamgSensorEntityDescription(
        key="wind_max_speed",
        name="Top Wind Speed",
        native_unit_of_measurement=SPEED_KILOMETERS_PER_HOUR,
        col_heading=f"WSG {SPEED_KILOMETERS_PER_HOUR}",
        dtype=float,
    ),
    ZamgSensorEntityDescription(
        key="wind_max_bearing",
        name="Top Wind Bearing",
        native_unit_of_measurement=DEGREE,
        col_heading=f"WSR {DEGREE}",
        dtype=int,
    ),
    ZamgSensorEntityDescription(
        key="sun_last_hour",
        name="Sun Last Hour",
        native_unit_of_measurement=PERCENTAGE,
        col_heading=f"SO {PERCENTAGE}",
        dtype=int,
    ),
    ZamgSensorEntityDescription(
        key="temperature",
        name="Temperature",
        native_unit_of_measurement=TEMP_CELSIUS,
        device_class=SensorDeviceClass.TEMPERATURE,
        col_heading=f"T {TEMP_CELSIUS}",
        dtype=float,
    ),
    ZamgSensorEntityDescription(
        key="precipitation",
        name="Precipitation",
        native_unit_of_measurement=f"l/{AREA_SQUARE_METERS}",
        col_heading=f"N l/{AREA_SQUARE_METERS}",
        dtype=float,
    ),
    ZamgSensorEntityDescription(
        key="dewpoint",
        name="Dew Point",
        native_unit_of_measurement=TEMP_CELSIUS,
        device_class=SensorDeviceClass.TEMPERATURE,
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
        _LOGGER.error("Received error from ZAMG: %s", err)
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


class ZamgSensor(SensorEntity):
    """Implementation of a ZAMG sensor."""

    _attr_attribution = ATTRIBUTION
    entity_description: ZamgSensorEntityDescription

    def __init__(self, probe, name, description: ZamgSensorEntityDescription):
        """Initialize the sensor."""
        self.entity_description = description
        self.probe = probe
        self._attr_name = f"{name} {description.key}"

    @property
    def native_value(self):
        """Return the state of the sensor."""
        return self.probe.get_data(self.entity_description.key)

    @property
    def extra_state_attributes(self):
        """Return the state attributes."""
        return {
            ATTR_STATION: self.probe.get_data("station_name"),
            ATTR_UPDATED: self.probe.last_update.isoformat(),
        }

    def update(self):
        """Delegate update to probe."""
        self.probe.update()


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
