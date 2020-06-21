"""Support for the Netatmo Weather Service."""
from datetime import timedelta
import logging

import pyatmo

from homeassistant.const import (
    CONCENTRATION_PARTS_PER_MILLION,
    DEVICE_CLASS_BATTERY,
    DEVICE_CLASS_HUMIDITY,
    DEVICE_CLASS_TEMPERATURE,
    SPEED_KILOMETERS_PER_HOUR,
    TEMP_CELSIUS,
    UNIT_PERCENTAGE,
)
from homeassistant.helpers.entity import Entity
from homeassistant.util import Throttle

from .const import AUTH, DOMAIN, MANUFACTURER, MODELS

_LOGGER = logging.getLogger(__name__)

CONF_MODULES = "modules"
CONF_STATION = "station"
CONF_AREAS = "areas"
CONF_LAT_NE = "lat_ne"
CONF_LON_NE = "lon_ne"
CONF_LAT_SW = "lat_sw"
CONF_LON_SW = "lon_sw"

DEFAULT_MODE = "avg"
MODE_TYPES = {"max", "avg"}

# This is the Netatmo data upload interval in seconds
NETATMO_UPDATE_INTERVAL = 600

# NetAtmo Public Data is uploaded to server every 10 minutes
MIN_TIME_BETWEEN_UPDATES = timedelta(seconds=NETATMO_UPDATE_INTERVAL)

SUPPORTED_PUBLIC_SENSOR_TYPES = [
    "temperature",
    "pressure",
    "humidity",
    "rain",
    "windstrength",
    "guststrength",
    "sum_rain_1",
    "sum_rain_24",
]

SENSOR_TYPES = {
    "temperature": [
        "Temperature",
        TEMP_CELSIUS,
        "mdi:thermometer",
        DEVICE_CLASS_TEMPERATURE,
    ],
    "co2": ["CO2", CONCENTRATION_PARTS_PER_MILLION, "mdi:periodic-table-co2", None],
    "pressure": ["Pressure", "mbar", "mdi:gauge", None],
    "noise": ["Noise", "dB", "mdi:volume-high", None],
    "humidity": [
        "Humidity",
        UNIT_PERCENTAGE,
        "mdi:water-percent",
        DEVICE_CLASS_HUMIDITY,
    ],
    "rain": ["Rain", "mm", "mdi:weather-rainy", None],
    "sum_rain_1": ["sum_rain_1", "mm", "mdi:weather-rainy", None],
    "sum_rain_24": ["sum_rain_24", "mm", "mdi:weather-rainy", None],
    "battery_vp": ["Battery", "", "mdi:battery", None],
    "battery_lvl": ["Battery_lvl", "", "mdi:battery", None],
    "battery_percent": ["battery_percent", UNIT_PERCENTAGE, None, DEVICE_CLASS_BATTERY],
    "min_temp": ["Min Temp.", TEMP_CELSIUS, "mdi:thermometer", None],
    "max_temp": ["Max Temp.", TEMP_CELSIUS, "mdi:thermometer", None],
    "windangle": ["Angle", "", "mdi:compass", None],
    "windangle_value": ["Angle Value", "º", "mdi:compass", None],
    "windstrength": [
        "Wind Strength",
        SPEED_KILOMETERS_PER_HOUR,
        "mdi:weather-windy",
        None,
    ],
    "gustangle": ["Gust Angle", "", "mdi:compass", None],
    "gustangle_value": ["Gust Angle Value", "º", "mdi:compass", None],
    "guststrength": [
        "Gust Strength",
        SPEED_KILOMETERS_PER_HOUR,
        "mdi:weather-windy",
        None,
    ],
    "reachable": ["Reachability", "", "mdi:signal", None],
    "rf_status": ["Radio", "", "mdi:signal", None],
    "rf_status_lvl": ["Radio_lvl", "", "mdi:signal", None],
    "wifi_status": ["Wifi", "", "mdi:wifi", None],
    "wifi_status_lvl": ["Wifi_lvl", "dBm", "mdi:wifi", None],
    "health_idx": ["Health", "", "mdi:cloud", None],
}

MODULE_TYPE_OUTDOOR = "NAModule1"
MODULE_TYPE_WIND = "NAModule2"
MODULE_TYPE_RAIN = "NAModule3"
MODULE_TYPE_INDOOR = "NAModule4"


NETATMO_DEVICE_TYPES = {
    "WeatherStationData": "weather station",
    "HomeCoachData": "home coach",
}


async def async_setup_entry(hass, entry, async_add_entities):
    """Set up the Netatmo weather and homecoach platform."""
    auth = hass.data[DOMAIN][entry.entry_id][AUTH]

    def find_entities(data):
        """Find all entities."""
        all_module_infos = data.get_module_infos()
        entities = []
        for module in all_module_infos.values():
            _LOGGER.debug("Adding module %s %s", module["module_name"], module["id"])
            for condition in data.station_data.monitoredConditions(
                moduleId=module["id"]
            ):
                entities.append(NetatmoSensor(data, module, condition.lower()))
        return entities

    def get_entities():
        """Retrieve Netatmo entities."""
        entities = []

        for data_class in [pyatmo.WeatherStationData, pyatmo.HomeCoachData]:
            try:
                dc_data = data_class(auth)
                _LOGGER.debug("%s detected!", NETATMO_DEVICE_TYPES[data_class.__name__])
                data = NetatmoData(auth, dc_data)
            except pyatmo.NoDevice:
                _LOGGER.debug(
                    "No %s entities found", NETATMO_DEVICE_TYPES[data_class.__name__]
                )
                continue

            entities.extend(find_entities(data))

        return entities

    async_add_entities(await hass.async_add_executor_job(get_entities), True)


async def async_setup_platform(hass, config, async_add_entities, discovery_info=None):
    """Set up the Netatmo weather and homecoach platform."""
    return


class NetatmoSensor(Entity):
    """Implementation of a Netatmo sensor."""

    def __init__(self, netatmo_data, module_info, sensor_type):
        """Initialize the sensor."""
        self.netatmo_data = netatmo_data

        device = self.netatmo_data.station_data.moduleById(mid=module_info["id"])
        if not device:
            # Assume it's a station if module can't be found
            device = self.netatmo_data.station_data.stationById(sid=module_info["id"])

        if device["type"] == "NHC":
            self.module_name = module_info["station_name"]
        else:
            self.module_name = (
                f"{module_info['station_name']} {module_info['module_name']}"
            )

        self._name = f"{MANUFACTURER} {self.module_name} {SENSOR_TYPES[sensor_type][0]}"
        self.type = sensor_type
        self._state = None
        self._device_class = SENSOR_TYPES[self.type][3]
        self._icon = SENSOR_TYPES[self.type][2]
        self._unit_of_measurement = SENSOR_TYPES[self.type][1]
        self._module_type = device["type"]
        self._module_id = module_info["id"]
        self._unique_id = f"{self._module_id}-{self.type}"

    @property
    def name(self):
        """Return the name of the sensor."""
        return self._name

    @property
    def icon(self):
        """Icon to use in the frontend, if any."""
        return self._icon

    @property
    def device_class(self):
        """Return the device class of the sensor."""
        return self._device_class

    @property
    def device_info(self):
        """Return the device info for the sensor."""
        return {
            "identifiers": {(DOMAIN, self._module_id)},
            "name": self.module_name,
            "manufacturer": MANUFACTURER,
            "model": MODELS[self._module_type],
        }

    @property
    def state(self):
        """Return the state of the device."""
        return self._state

    @property
    def unit_of_measurement(self):
        """Return the unit of measurement of this entity, if any."""
        return self._unit_of_measurement

    @property
    def unique_id(self):
        """Return the unique ID for this sensor."""
        return self._unique_id

    @property
    def available(self):
        """Return True if entity is available."""
        return self._state is not None

    def update(self):
        """Get the latest data from Netatmo API and updates the states."""
        self.netatmo_data.update()
        if self.netatmo_data.data is None:
            if self._state is None:
                return
            _LOGGER.warning("No data from update")
            self._state = None
            return

        data = self.netatmo_data.data.get(self._module_id)

        if data is None:
            if self._state:
                _LOGGER.debug(
                    "No data found for %s (%s)", self.module_name, self._module_id
                )
                _LOGGER.debug("data: %s", self.netatmo_data.data)
            self._state = None
            return

        try:
            if self.type == "temperature":
                self._state = round(data["Temperature"], 1)
            elif self.type == "humidity":
                self._state = data["Humidity"]
            elif self.type == "rain":
                self._state = data["Rain"]
            elif self.type == "sum_rain_1":
                self._state = round(data["sum_rain_1"], 1)
            elif self.type == "sum_rain_24":
                self._state = data["sum_rain_24"]
            elif self.type == "noise":
                self._state = data["Noise"]
            elif self.type == "co2":
                self._state = data["CO2"]
            elif self.type == "pressure":
                self._state = round(data["Pressure"], 1)
            elif self.type == "battery_percent":
                self._state = data["battery_percent"]
            elif self.type == "battery_lvl":
                self._state = data["battery_vp"]
            elif self.type == "battery_vp" and self._module_type == MODULE_TYPE_WIND:
                if data["battery_vp"] >= 5590:
                    self._state = "Full"
                elif data["battery_vp"] >= 5180:
                    self._state = "High"
                elif data["battery_vp"] >= 4770:
                    self._state = "Medium"
                elif data["battery_vp"] >= 4360:
                    self._state = "Low"
                elif data["battery_vp"] < 4360:
                    self._state = "Very Low"
            elif self.type == "battery_vp" and self._module_type == MODULE_TYPE_RAIN:
                if data["battery_vp"] >= 5500:
                    self._state = "Full"
                elif data["battery_vp"] >= 5000:
                    self._state = "High"
                elif data["battery_vp"] >= 4500:
                    self._state = "Medium"
                elif data["battery_vp"] >= 4000:
                    self._state = "Low"
                elif data["battery_vp"] < 4000:
                    self._state = "Very Low"
            elif self.type == "battery_vp" and self._module_type == MODULE_TYPE_INDOOR:
                if data["battery_vp"] >= 5640:
                    self._state = "Full"
                elif data["battery_vp"] >= 5280:
                    self._state = "High"
                elif data["battery_vp"] >= 4920:
                    self._state = "Medium"
                elif data["battery_vp"] >= 4560:
                    self._state = "Low"
                elif data["battery_vp"] < 4560:
                    self._state = "Very Low"
            elif self.type == "battery_vp" and self._module_type == MODULE_TYPE_OUTDOOR:
                if data["battery_vp"] >= 5500:
                    self._state = "Full"
                elif data["battery_vp"] >= 5000:
                    self._state = "High"
                elif data["battery_vp"] >= 4500:
                    self._state = "Medium"
                elif data["battery_vp"] >= 4000:
                    self._state = "Low"
                elif data["battery_vp"] < 4000:
                    self._state = "Very Low"
            elif self.type == "min_temp":
                self._state = data["min_temp"]
            elif self.type == "max_temp":
                self._state = data["max_temp"]
            elif self.type == "windangle_value":
                self._state = data["WindAngle"]
            elif self.type == "windangle":
                if data["WindAngle"] >= 330:
                    self._state = "N (%d\xb0)" % data["WindAngle"]
                elif data["WindAngle"] >= 300:
                    self._state = "NW (%d\xb0)" % data["WindAngle"]
                elif data["WindAngle"] >= 240:
                    self._state = "W (%d\xb0)" % data["WindAngle"]
                elif data["WindAngle"] >= 210:
                    self._state = "SW (%d\xb0)" % data["WindAngle"]
                elif data["WindAngle"] >= 150:
                    self._state = "S (%d\xb0)" % data["WindAngle"]
                elif data["WindAngle"] >= 120:
                    self._state = "SE (%d\xb0)" % data["WindAngle"]
                elif data["WindAngle"] >= 60:
                    self._state = "E (%d\xb0)" % data["WindAngle"]
                elif data["WindAngle"] >= 30:
                    self._state = "NE (%d\xb0)" % data["WindAngle"]
                elif data["WindAngle"] >= 0:
                    self._state = "N (%d\xb0)" % data["WindAngle"]
            elif self.type == "windstrength":
                self._state = data["WindStrength"]
            elif self.type == "gustangle_value":
                self._state = data["GustAngle"]
            elif self.type == "gustangle":
                if data["GustAngle"] >= 330:
                    self._state = "N (%d\xb0)" % data["GustAngle"]
                elif data["GustAngle"] >= 300:
                    self._state = "NW (%d\xb0)" % data["GustAngle"]
                elif data["GustAngle"] >= 240:
                    self._state = "W (%d\xb0)" % data["GustAngle"]
                elif data["GustAngle"] >= 210:
                    self._state = "SW (%d\xb0)" % data["GustAngle"]
                elif data["GustAngle"] >= 150:
                    self._state = "S (%d\xb0)" % data["GustAngle"]
                elif data["GustAngle"] >= 120:
                    self._state = "SE (%d\xb0)" % data["GustAngle"]
                elif data["GustAngle"] >= 60:
                    self._state = "E (%d\xb0)" % data["GustAngle"]
                elif data["GustAngle"] >= 30:
                    self._state = "NE (%d\xb0)" % data["GustAngle"]
                elif data["GustAngle"] >= 0:
                    self._state = "N (%d\xb0)" % data["GustAngle"]
            elif self.type == "guststrength":
                self._state = data["GustStrength"]
            elif self.type == "reachable":
                self._state = data["reachable"]
            elif self.type == "rf_status_lvl":
                self._state = data["rf_status"]
            elif self.type == "rf_status":
                if data["rf_status"] >= 90:
                    self._state = "Low"
                elif data["rf_status"] >= 76:
                    self._state = "Medium"
                elif data["rf_status"] >= 60:
                    self._state = "High"
                elif data["rf_status"] <= 59:
                    self._state = "Full"
            elif self.type == "wifi_status_lvl":
                self._state = data["wifi_status"]
            elif self.type == "wifi_status":
                if data["wifi_status"] >= 86:
                    self._state = "Low"
                elif data["wifi_status"] >= 71:
                    self._state = "Medium"
                elif data["wifi_status"] >= 56:
                    self._state = "High"
                elif data["wifi_status"] <= 55:
                    self._state = "Full"
            elif self.type == "health_idx":
                if data["health_idx"] == 0:
                    self._state = "Healthy"
                elif data["health_idx"] == 1:
                    self._state = "Fine"
                elif data["health_idx"] == 2:
                    self._state = "Fair"
                elif data["health_idx"] == 3:
                    self._state = "Poor"
                elif data["health_idx"] == 4:
                    self._state = "Unhealthy"
        except KeyError:
            if self._state:
                _LOGGER.info("No %s data found for %s", self.type, self.module_name)
            self._state = None
            return


class NetatmoPublicSensor(Entity):
    """Represent a single sensor in a Netatmo."""

    def __init__(self, area_name, data, sensor_type, mode):
        """Initialize the sensor."""
        self.netatmo_data = data
        self.type = sensor_type
        self._mode = mode
        self._name = f"{MANUFACTURER} {area_name} {SENSOR_TYPES[self.type][0]}"
        self._area_name = area_name
        self._state = None
        self._device_class = SENSOR_TYPES[self.type][3]
        self._icon = SENSOR_TYPES[self.type][2]
        self._unit_of_measurement = SENSOR_TYPES[self.type][1]

    @property
    def name(self):
        """Return the name of the sensor."""
        return self._name

    @property
    def icon(self):
        """Icon to use in the frontend."""
        return self._icon

    @property
    def device_class(self):
        """Return the device class of the sensor."""
        return self._device_class

    @property
    def device_info(self):
        """Return the device info for the sensor."""
        return {
            "identifiers": {(DOMAIN, self._area_name)},
            "name": self._area_name,
            "manufacturer": MANUFACTURER,
            "model": "public",
        }

    @property
    def state(self):
        """Return the state of the device."""
        return self._state

    @property
    def unit_of_measurement(self):
        """Return the unit of measurement of this entity."""
        return self._unit_of_measurement

    @property
    def available(self):
        """Return True if entity is available."""
        return bool(self._state)

    def update(self):
        """Get the latest data from Netatmo API and updates the states."""
        self.netatmo_data.update()

        if self.netatmo_data.data is None:
            _LOGGER.info("No data found for %s", self._name)
            self._state = None
            return

        data = None

        if self.type == "temperature":
            data = self.netatmo_data.data.getLatestTemperatures()
        elif self.type == "pressure":
            data = self.netatmo_data.data.getLatestPressures()
        elif self.type == "humidity":
            data = self.netatmo_data.data.getLatestHumidities()
        elif self.type == "rain":
            data = self.netatmo_data.data.getLatestRain()
        elif self.type == "sum_rain_1":
            data = self.netatmo_data.data.get60minRain()
        elif self.type == "sum_rain_24":
            data = self.netatmo_data.data.get24hRain()
        elif self.type == "windstrength":
            data = self.netatmo_data.data.getLatestWindStrengths()
        elif self.type == "guststrength":
            data = self.netatmo_data.data.getLatestGustStrengths()

        if not data:
            _LOGGER.warning(
                "No station provides %s data in the area %s", self.type, self._area_name
            )
            self._state = None
            return

        values = [x for x in data.values() if x is not None]
        if self._mode == "avg":
            self._state = round(sum(values) / len(values), 1)
        elif self._mode == "max":
            self._state = max(values)


class NetatmoPublicData:
    """Get the latest data from Netatmo."""

    def __init__(self, auth, lat_ne, lon_ne, lat_sw, lon_sw):
        """Initialize the data object."""
        self.auth = auth
        self.data = None
        self.lat_ne = lat_ne
        self.lon_ne = lon_ne
        self.lat_sw = lat_sw
        self.lon_sw = lon_sw

    @Throttle(MIN_TIME_BETWEEN_UPDATES)
    def update(self):
        """Request an update from the Netatmo API."""
        try:
            data = pyatmo.PublicData(
                self.auth,
                LAT_NE=self.lat_ne,
                LON_NE=self.lon_ne,
                LAT_SW=self.lat_sw,
                LON_SW=self.lon_sw,
                filtering=True,
            )
        except pyatmo.NoDevice:
            data = None

        if not data:
            _LOGGER.debug("No data received when updating public station data")
            return

        if data.CountStationInArea() == 0:
            _LOGGER.warning("No Stations available in this area.")
            return

        self.data = data


class NetatmoData:
    """Get the latest data from Netatmo."""

    def __init__(self, auth, station_data):
        """Initialize the data object."""
        self.data = {}
        self.station_data = station_data
        self.auth = auth

    def get_module_infos(self):
        """Return all modules available on the API as a dict."""
        return self.station_data.getModules()

    @Throttle(MIN_TIME_BETWEEN_UPDATES)
    def update(self):
        """Call the Netatmo API to update the data."""
        self.station_data = self.station_data.__class__(self.auth)

        data = self.station_data.lastData(exclude=3600, byId=True)
        if not data:
            _LOGGER.debug("No data received when updating station data")
            return
        self.data = data
