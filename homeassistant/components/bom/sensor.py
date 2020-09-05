"""Support for Australian BOM (Bureau of Meteorology) weather service."""
import datetime
import ftplib
import gzip
import io
import json
import logging
import os
import re
import zipfile

import requests
import voluptuous as vol

from homeassistant.components.sensor import PLATFORM_SCHEMA
from homeassistant.const import (
    ATTR_ATTRIBUTION,
    CONF_LATITUDE,
    CONF_LONGITUDE,
    CONF_MONITORED_CONDITIONS,
    CONF_NAME,
    LENGTH_KILOMETERS,
    LENGTH_METERS,
    SPEED_KILOMETERS_PER_HOUR,
    TEMP_CELSIUS,
    UNIT_PERCENTAGE,
)
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.entity import Entity
from homeassistant.util import Throttle
import homeassistant.util.dt as dt_util

_LOGGER = logging.getLogger(__name__)

ATTR_LAST_UPDATE = "last_update"
ATTR_SENSOR_ID = "sensor_id"
ATTR_STATION_ID = "station_id"
ATTR_STATION_NAME = "station_name"
ATTR_ZONE_ID = "zone_id"

ATTRIBUTION = "Data provided by the Australian Bureau of Meteorology"

CONF_STATION = "station"
CONF_ZONE_ID = "zone_id"
CONF_WMO_ID = "wmo_id"

MIN_TIME_BETWEEN_UPDATES = datetime.timedelta(seconds=60)

SENSOR_TYPES = {
    "wmo": ["wmo", None],
    "name": ["Station Name", None],
    "history_product": ["Zone", None],
    "local_date_time": ["Local Time", None],
    "local_date_time_full": ["Local Time Full", None],
    "aifstime_utc": ["UTC Time Full", None],
    "lat": ["Lat", None],
    "lon": ["Long", None],
    "apparent_t": ["Feels Like C", TEMP_CELSIUS],
    "cloud": ["Cloud", None],
    "cloud_base_m": ["Cloud Base", None],
    "cloud_oktas": ["Cloud Oktas", None],
    "cloud_type_id": ["Cloud Type ID", None],
    "cloud_type": ["Cloud Type", None],
    "delta_t": ["Delta Temp C", TEMP_CELSIUS],
    "gust_kmh": ["Wind Gust kmh", SPEED_KILOMETERS_PER_HOUR],
    "gust_kt": ["Wind Gust kt", "kt"],
    "air_temp": ["Air Temp C", TEMP_CELSIUS],
    "dewpt": ["Dew Point C", TEMP_CELSIUS],
    "press": ["Pressure mb", "mbar"],
    "press_qnh": ["Pressure qnh", "qnh"],
    "press_msl": ["Pressure msl", "msl"],
    "press_tend": ["Pressure Tend", None],
    "rain_trace": ["Rain Today", "mm"],
    "rel_hum": ["Relative Humidity", UNIT_PERCENTAGE],
    "sea_state": ["Sea State", None],
    "swell_dir_worded": ["Swell Direction", None],
    "swell_height": ["Swell Height", LENGTH_METERS],
    "swell_period": ["Swell Period", None],
    "vis_km": [f"Visability {LENGTH_KILOMETERS}", LENGTH_KILOMETERS],
    "weather": ["Weather", None],
    "wind_dir": ["Wind Direction", None],
    "wind_spd_kmh": ["Wind Speed kmh", SPEED_KILOMETERS_PER_HOUR],
    "wind_spd_kt": ["Wind Speed kt", "kt"],
}


def validate_station(station):
    """Check that the station ID is well-formed."""
    if station is None:
        return
    station = station.replace(".shtml", "")
    if not re.fullmatch(r"ID[A-Z]\d\d\d\d\d\.\d\d\d\d\d", station):
        raise vol.error.Invalid("Malformed station ID")
    return station


PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {
        vol.Inclusive(CONF_ZONE_ID, "Deprecated partial station ID"): cv.string,
        vol.Inclusive(CONF_WMO_ID, "Deprecated partial station ID"): cv.string,
        vol.Optional(CONF_NAME): cv.string,
        vol.Optional(CONF_STATION): validate_station,
        vol.Required(CONF_MONITORED_CONDITIONS, default=[]): vol.All(
            cv.ensure_list, [vol.In(SENSOR_TYPES)]
        ),
    }
)


def setup_platform(hass, config, add_entities, discovery_info=None):
    """Set up the BOM sensor."""
    station = config.get(CONF_STATION)
    zone_id, wmo_id = config.get(CONF_ZONE_ID), config.get(CONF_WMO_ID)

    if station is not None:
        if zone_id and wmo_id:
            _LOGGER.warning(
                "Using configuration %s, not %s and %s for BOM sensor",
                CONF_STATION,
                CONF_ZONE_ID,
                CONF_WMO_ID,
            )
    elif zone_id and wmo_id:
        station = f"{zone_id}.{wmo_id}"
    else:
        station = closest_station(
            config.get(CONF_LATITUDE),
            config.get(CONF_LONGITUDE),
            hass.config.config_dir,
        )
        if station is None:
            _LOGGER.error("Could not get BOM weather station from lat/lon")
            return

    bom_data = BOMCurrentData(station)

    try:
        bom_data.update()
    except ValueError as err:
        _LOGGER.error("Received error from BOM Current: %s", err)
        return

    add_entities(
        [
            BOMCurrentSensor(bom_data, variable, config.get(CONF_NAME))
            for variable in config[CONF_MONITORED_CONDITIONS]
        ]
    )


class BOMCurrentSensor(Entity):
    """Implementation of a BOM current sensor."""

    def __init__(self, bom_data, condition, stationname):
        """Initialize the sensor."""
        self.bom_data = bom_data
        self._condition = condition
        self.stationname = stationname

    @property
    def name(self):
        """Return the name of the sensor."""
        if self.stationname is None:
            return f"BOM {SENSOR_TYPES[self._condition][0]}"

        return f"BOM {self.stationname} {SENSOR_TYPES[self._condition][0]}"

    @property
    def state(self):
        """Return the state of the sensor."""
        return self.bom_data.get_reading(self._condition)

    @property
    def device_state_attributes(self):
        """Return the state attributes of the device."""
        attr = {
            ATTR_ATTRIBUTION: ATTRIBUTION,
            ATTR_LAST_UPDATE: self.bom_data.last_updated,
            ATTR_SENSOR_ID: self._condition,
            ATTR_STATION_ID: self.bom_data.latest_data["wmo"],
            ATTR_STATION_NAME: self.bom_data.latest_data["name"],
            ATTR_ZONE_ID: self.bom_data.latest_data["history_product"],
        }

        return attr

    @property
    def unit_of_measurement(self):
        """Return the units of measurement."""
        return SENSOR_TYPES[self._condition][1]

    def update(self):
        """Update current conditions."""
        self.bom_data.update()


class BOMCurrentData:
    """Get data from BOM."""

    def __init__(self, station_id):
        """Initialize the data object."""
        self._zone_id, self._wmo_id = station_id.split(".")
        self._data = None
        self.last_updated = None

    def _build_url(self):
        """Build the URL for the requests."""
        url = (
            f"http://www.bom.gov.au/fwo/{self._zone_id}"
            f"/{self._zone_id}.{self._wmo_id}.json"
        )
        _LOGGER.debug("BOM URL: %s", url)
        return url

    @property
    def latest_data(self):
        """Return the latest data object."""
        if self._data:
            return self._data[0]
        return None

    def get_reading(self, condition):
        """Return the value for the given condition.

        BOM weather publishes condition readings for weather (and a few other
        conditions) at intervals throughout the day. To avoid a `-` value in
        the frontend for these conditions, we traverse the historical data
        for the latest value that is not `-`.

        Iterators are used in this method to avoid iterating needlessly
        through the entire BOM provided dataset.
        """
        condition_readings = (entry[condition] for entry in self._data)
        reading = next((x for x in condition_readings if x != "-"), None)

        if isinstance(reading, (int, float)):
            return round(reading, 2)
        return reading

    def should_update(self):
        """Determine whether an update should occur.

        BOM provides updated data every 30 minutes. We manually define
        refreshing logic here rather than a throttle to keep updates
        in lock-step with BOM.

        If 35 minutes has passed since the last BOM data update, then
        an update should be done.
        """
        if self.last_updated is None:
            # Never updated before, therefore an update should occur.
            return True

        now = dt_util.utcnow()
        update_due_at = self.last_updated + datetime.timedelta(minutes=35)
        return now > update_due_at

    @Throttle(MIN_TIME_BETWEEN_UPDATES)
    def update(self):
        """Get the latest data from BOM."""
        if not self.should_update():
            _LOGGER.debug(
                "BOM was updated %s minutes ago, skipping update as"
                " < 35 minutes, Now: %s, LastUpdate: %s",
                (dt_util.utcnow() - self.last_updated),
                dt_util.utcnow(),
                self.last_updated,
            )
            return

        try:
            result = requests.get(self._build_url(), timeout=10).json()
            self._data = result["observations"]["data"]

            # set lastupdate using self._data[0] as the first element in the
            # array is the latest date in the json
            self.last_updated = dt_util.as_utc(
                datetime.datetime.strptime(
                    str(self._data[0]["local_date_time_full"]), "%Y%m%d%H%M%S"
                )
            )
            return

        except ValueError as err:
            _LOGGER.error("Check BOM %s", err.args)
            self._data = None
            raise


def _get_bom_stations():
    """Return {CONF_STATION: (lat, lon)} for all stations, for auto-config.

    This function does several MB of internet requests, so please use the
    caching version to minimize latency and hit-count.
    """
    latlon = {}
    with io.BytesIO() as file_obj:
        with ftplib.FTP("ftp.bom.gov.au") as ftp:
            ftp.login()
            ftp.cwd("anon2/home/ncc/metadata/sitelists")
            ftp.retrbinary("RETR stations.zip", file_obj.write)
        file_obj.seek(0)
        with zipfile.ZipFile(file_obj) as zipped:
            with zipped.open("stations.txt") as station_txt:
                for _ in range(4):
                    station_txt.readline()  # skip header
                while True:
                    line = station_txt.readline().decode().strip()
                    if len(line) < 120:
                        break  # end while loop, ignoring any footer text
                    wmo, lat, lon = (
                        line[a:b].strip() for a, b in [(128, 134), (70, 78), (79, 88)]
                    )
                    if wmo != "..":
                        latlon[wmo] = (float(lat), float(lon))
    zones = {}
    pattern = (
        r'<a href="/products/(?P<zone>ID[A-Z]\d\d\d\d\d)/'
        r'(?P=zone)\.(?P<wmo>\d\d\d\d\d).shtml">'
    )
    for state in ("nsw", "vic", "qld", "wa", "tas", "nt"):
        url = f"http://www.bom.gov.au/{state}/observations/{state}all.shtml"
        for zone_id, wmo_id in re.findall(pattern, requests.get(url).text):
            zones[wmo_id] = zone_id
    return {f"{zones[k]}.{k}": latlon[k] for k in set(latlon) & set(zones)}


def bom_stations(cache_dir):
    """Return {CONF_STATION: (lat, lon)} for all stations, for auto-config.

    Results from internet requests are cached as compressed JSON, making
    subsequent calls very much faster.
    """
    cache_file = os.path.join(cache_dir, ".bom-stations.json.gz")
    if not os.path.isfile(cache_file):
        stations = _get_bom_stations()
        with gzip.open(cache_file, "wt") as cache:
            json.dump(stations, cache, sort_keys=True)
        return stations
    with gzip.open(cache_file, "rt") as cache:
        return {k: tuple(v) for k, v in json.load(cache).items()}


def closest_station(lat, lon, cache_dir):
    """Return the ZONE_ID.WMO_ID of the closest station to our lat/lon."""
    if lat is None or lon is None or not os.path.isdir(cache_dir):
        return
    stations = bom_stations(cache_dir)

    def comparable_dist(wmo_id):
        """Create a psudeo-distance from latitude/longitude."""
        station_lat, station_lon = stations[wmo_id]
        return (lat - station_lat) ** 2 + (lon - station_lon) ** 2

    return min(stations, key=comparable_dist)
