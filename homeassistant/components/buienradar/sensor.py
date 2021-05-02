"""Support for Buienradar.nl weather service."""
import logging

from buienradar.constants import (
    ATTRIBUTION,
    CONDCODE,
    CONDITION,
    DETAILED,
    EXACT,
    EXACTNL,
    FORECAST,
    IMAGE,
    MEASURED,
    PRECIPITATION_FORECAST,
    STATIONNAME,
    TIMEFRAME,
    VISIBILITY,
    WINDGUST,
    WINDSPEED,
)

from homeassistant.components.sensor import SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    ATTR_ATTRIBUTION,
    CONF_LATITUDE,
    CONF_LONGITUDE,
    CONF_NAME,
    DEGREE,
    IRRADIATION_WATTS_PER_SQUARE_METER,
    LENGTH_KILOMETERS,
    LENGTH_MILLIMETERS,
    PERCENTAGE,
    PRECIPITATION_MILLIMETERS_PER_HOUR,
    PRESSURE_HPA,
    SPEED_KILOMETERS_PER_HOUR,
    TEMP_CELSIUS,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.util import dt as dt_util

from .const import CONF_TIMEFRAME, DEFAULT_TIMEFRAME
from .util import BrData

_LOGGER = logging.getLogger(__name__)

MEASURED_LABEL = "Measured"
TIMEFRAME_LABEL = "Timeframe"
SYMBOL = "symbol"

# Schedule next call after (minutes):
SCHEDULE_OK = 10
# When an error occurred, new call after (minutes):
SCHEDULE_NOK = 2

# Supported sensor types:
# Key: ['label', unit, icon]
SENSOR_TYPES = {
    "stationname": ["Stationname", None, None],
    # new in json api (>1.0.0):
    "barometerfc": ["Barometer value", None, "mdi:gauge"],
    # new in json api (>1.0.0):
    "barometerfcname": ["Barometer", None, "mdi:gauge"],
    # new in json api (>1.0.0):
    "barometerfcnamenl": ["Barometer", None, "mdi:gauge"],
    "condition": ["Condition", None, None],
    "conditioncode": ["Condition code", None, None],
    "conditiondetailed": ["Detailed condition", None, None],
    "conditionexact": ["Full condition", None, None],
    "symbol": ["Symbol", None, None],
    # new in json api (>1.0.0):
    "feeltemperature": ["Feel temperature", TEMP_CELSIUS, "mdi:thermometer"],
    "humidity": ["Humidity", PERCENTAGE, "mdi:water-percent"],
    "temperature": ["Temperature", TEMP_CELSIUS, "mdi:thermometer"],
    "groundtemperature": ["Ground temperature", TEMP_CELSIUS, "mdi:thermometer"],
    "windspeed": ["Wind speed", SPEED_KILOMETERS_PER_HOUR, "mdi:weather-windy"],
    "windforce": ["Wind force", "Bft", "mdi:weather-windy"],
    "winddirection": ["Wind direction", None, "mdi:compass-outline"],
    "windazimuth": ["Wind direction azimuth", DEGREE, "mdi:compass-outline"],
    "pressure": ["Pressure", PRESSURE_HPA, "mdi:gauge"],
    "visibility": ["Visibility", LENGTH_KILOMETERS, None],
    "windgust": ["Wind gust", SPEED_KILOMETERS_PER_HOUR, "mdi:weather-windy"],
    "precipitation": [
        "Precipitation",
        PRECIPITATION_MILLIMETERS_PER_HOUR,
        "mdi:weather-pouring",
    ],
    "irradiance": ["Irradiance", IRRADIATION_WATTS_PER_SQUARE_METER, "mdi:sunglasses"],
    "precipitation_forecast_average": [
        "Precipitation forecast average",
        PRECIPITATION_MILLIMETERS_PER_HOUR,
        "mdi:weather-pouring",
    ],
    "precipitation_forecast_total": [
        "Precipitation forecast total",
        LENGTH_MILLIMETERS,
        "mdi:weather-pouring",
    ],
    # new in json api (>1.0.0):
    "rainlast24hour": ["Rain last 24h", LENGTH_MILLIMETERS, "mdi:weather-pouring"],
    # new in json api (>1.0.0):
    "rainlasthour": ["Rain last hour", LENGTH_MILLIMETERS, "mdi:weather-pouring"],
    "temperature_1d": ["Temperature 1d", TEMP_CELSIUS, "mdi:thermometer"],
    "temperature_2d": ["Temperature 2d", TEMP_CELSIUS, "mdi:thermometer"],
    "temperature_3d": ["Temperature 3d", TEMP_CELSIUS, "mdi:thermometer"],
    "temperature_4d": ["Temperature 4d", TEMP_CELSIUS, "mdi:thermometer"],
    "temperature_5d": ["Temperature 5d", TEMP_CELSIUS, "mdi:thermometer"],
    "mintemp_1d": ["Minimum temperature 1d", TEMP_CELSIUS, "mdi:thermometer"],
    "mintemp_2d": ["Minimum temperature 2d", TEMP_CELSIUS, "mdi:thermometer"],
    "mintemp_3d": ["Minimum temperature 3d", TEMP_CELSIUS, "mdi:thermometer"],
    "mintemp_4d": ["Minimum temperature 4d", TEMP_CELSIUS, "mdi:thermometer"],
    "mintemp_5d": ["Minimum temperature 5d", TEMP_CELSIUS, "mdi:thermometer"],
    "rain_1d": ["Rain 1d", LENGTH_MILLIMETERS, "mdi:weather-pouring"],
    "rain_2d": ["Rain 2d", LENGTH_MILLIMETERS, "mdi:weather-pouring"],
    "rain_3d": ["Rain 3d", LENGTH_MILLIMETERS, "mdi:weather-pouring"],
    "rain_4d": ["Rain 4d", LENGTH_MILLIMETERS, "mdi:weather-pouring"],
    "rain_5d": ["Rain 5d", LENGTH_MILLIMETERS, "mdi:weather-pouring"],
    # new in json api (>1.0.0):
    "minrain_1d": ["Minimum rain 1d", LENGTH_MILLIMETERS, "mdi:weather-pouring"],
    "minrain_2d": ["Minimum rain 2d", LENGTH_MILLIMETERS, "mdi:weather-pouring"],
    "minrain_3d": ["Minimum rain 3d", LENGTH_MILLIMETERS, "mdi:weather-pouring"],
    "minrain_4d": ["Minimum rain 4d", LENGTH_MILLIMETERS, "mdi:weather-pouring"],
    "minrain_5d": ["Minimum rain 5d", LENGTH_MILLIMETERS, "mdi:weather-pouring"],
    # new in json api (>1.0.0):
    "maxrain_1d": ["Maximum rain 1d", LENGTH_MILLIMETERS, "mdi:weather-pouring"],
    "maxrain_2d": ["Maximum rain 2d", LENGTH_MILLIMETERS, "mdi:weather-pouring"],
    "maxrain_3d": ["Maximum rain 3d", LENGTH_MILLIMETERS, "mdi:weather-pouring"],
    "maxrain_4d": ["Maximum rain 4d", LENGTH_MILLIMETERS, "mdi:weather-pouring"],
    "maxrain_5d": ["Maximum rain 5d", LENGTH_MILLIMETERS, "mdi:weather-pouring"],
    "rainchance_1d": ["Rainchance 1d", PERCENTAGE, "mdi:weather-pouring"],
    "rainchance_2d": ["Rainchance 2d", PERCENTAGE, "mdi:weather-pouring"],
    "rainchance_3d": ["Rainchance 3d", PERCENTAGE, "mdi:weather-pouring"],
    "rainchance_4d": ["Rainchance 4d", PERCENTAGE, "mdi:weather-pouring"],
    "rainchance_5d": ["Rainchance 5d", PERCENTAGE, "mdi:weather-pouring"],
    "sunchance_1d": ["Sunchance 1d", PERCENTAGE, "mdi:weather-partly-cloudy"],
    "sunchance_2d": ["Sunchance 2d", PERCENTAGE, "mdi:weather-partly-cloudy"],
    "sunchance_3d": ["Sunchance 3d", PERCENTAGE, "mdi:weather-partly-cloudy"],
    "sunchance_4d": ["Sunchance 4d", PERCENTAGE, "mdi:weather-partly-cloudy"],
    "sunchance_5d": ["Sunchance 5d", PERCENTAGE, "mdi:weather-partly-cloudy"],
    "windforce_1d": ["Wind force 1d", "Bft", "mdi:weather-windy"],
    "windforce_2d": ["Wind force 2d", "Bft", "mdi:weather-windy"],
    "windforce_3d": ["Wind force 3d", "Bft", "mdi:weather-windy"],
    "windforce_4d": ["Wind force 4d", "Bft", "mdi:weather-windy"],
    "windforce_5d": ["Wind force 5d", "Bft", "mdi:weather-windy"],
    "windspeed_1d": ["Wind speed 1d", SPEED_KILOMETERS_PER_HOUR, "mdi:weather-windy"],
    "windspeed_2d": ["Wind speed 2d", SPEED_KILOMETERS_PER_HOUR, "mdi:weather-windy"],
    "windspeed_3d": ["Wind speed 3d", SPEED_KILOMETERS_PER_HOUR, "mdi:weather-windy"],
    "windspeed_4d": ["Wind speed 4d", SPEED_KILOMETERS_PER_HOUR, "mdi:weather-windy"],
    "windspeed_5d": ["Wind speed 5d", SPEED_KILOMETERS_PER_HOUR, "mdi:weather-windy"],
    "winddirection_1d": ["Wind direction 1d", None, "mdi:compass-outline"],
    "winddirection_2d": ["Wind direction 2d", None, "mdi:compass-outline"],
    "winddirection_3d": ["Wind direction 3d", None, "mdi:compass-outline"],
    "winddirection_4d": ["Wind direction 4d", None, "mdi:compass-outline"],
    "winddirection_5d": ["Wind direction 5d", None, "mdi:compass-outline"],
    "windazimuth_1d": ["Wind direction azimuth 1d", DEGREE, "mdi:compass-outline"],
    "windazimuth_2d": ["Wind direction azimuth 2d", DEGREE, "mdi:compass-outline"],
    "windazimuth_3d": ["Wind direction azimuth 3d", DEGREE, "mdi:compass-outline"],
    "windazimuth_4d": ["Wind direction azimuth 4d", DEGREE, "mdi:compass-outline"],
    "windazimuth_5d": ["Wind direction azimuth 5d", DEGREE, "mdi:compass-outline"],
    "condition_1d": ["Condition 1d", None, None],
    "condition_2d": ["Condition 2d", None, None],
    "condition_3d": ["Condition 3d", None, None],
    "condition_4d": ["Condition 4d", None, None],
    "condition_5d": ["Condition 5d", None, None],
    "conditioncode_1d": ["Condition code 1d", None, None],
    "conditioncode_2d": ["Condition code 2d", None, None],
    "conditioncode_3d": ["Condition code 3d", None, None],
    "conditioncode_4d": ["Condition code 4d", None, None],
    "conditioncode_5d": ["Condition code 5d", None, None],
    "conditiondetailed_1d": ["Detailed condition 1d", None, None],
    "conditiondetailed_2d": ["Detailed condition 2d", None, None],
    "conditiondetailed_3d": ["Detailed condition 3d", None, None],
    "conditiondetailed_4d": ["Detailed condition 4d", None, None],
    "conditiondetailed_5d": ["Detailed condition 5d", None, None],
    "conditionexact_1d": ["Full condition 1d", None, None],
    "conditionexact_2d": ["Full condition 2d", None, None],
    "conditionexact_3d": ["Full condition 3d", None, None],
    "conditionexact_4d": ["Full condition 4d", None, None],
    "conditionexact_5d": ["Full condition 5d", None, None],
    "symbol_1d": ["Symbol 1d", None, None],
    "symbol_2d": ["Symbol 2d", None, None],
    "symbol_3d": ["Symbol 3d", None, None],
    "symbol_4d": ["Symbol 4d", None, None],
    "symbol_5d": ["Symbol 5d", None, None],
}


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Create the buienradar sensor."""
    config = entry.data
    options = entry.options

    latitude = config.get(CONF_LATITUDE, hass.config.latitude)
    longitude = config.get(CONF_LONGITUDE, hass.config.longitude)

    timeframe = options.get(
        CONF_TIMEFRAME, config.get(CONF_TIMEFRAME, DEFAULT_TIMEFRAME)
    )

    if None in (latitude, longitude):
        _LOGGER.error("Latitude or longitude not set in Home Assistant config")
        return

    coordinates = {CONF_LATITUDE: float(latitude), CONF_LONGITUDE: float(longitude)}

    _LOGGER.debug(
        "Initializing buienradar sensor coordinate %s, timeframe %s",
        coordinates,
        timeframe,
    )

    entities = [
        BrSensor(sensor_type, config.get(CONF_NAME, "Buienradar"), coordinates)
        for sensor_type in SENSOR_TYPES
    ]

    async_add_entities(entities)

    data = BrData(hass, coordinates, timeframe, dev)
    # schedule the first update in 1 minute from now:
    await data.schedule_update(1)


class BrSensor(SensorEntity):
    """Representation of an Buienradar sensor."""

    def __init__(self, sensor_type, client_name, coordinates):
        """Initialize the sensor."""
        self.client_name = client_name
        self._name = SENSOR_TYPES[sensor_type][0]
        self.type = sensor_type
        self._state = None
        self._unit_of_measurement = SENSOR_TYPES[self.type][1]
        self._entity_picture = None
        self._attribution = None
        self._measured = None
        self._stationname = None
        self._unique_id = self.uid(coordinates)

        # All continuous sensors should be forced to be updated
        self._force_update = self.type != SYMBOL and not self.type.startswith(CONDITION)

        if self.type.startswith(PRECIPITATION_FORECAST):
            self._timeframe = None

    def uid(self, coordinates):
        """Generate a unique id using coordinates and sensor type."""
        # The combination of the location, name and sensor type is unique
        return "{:2.6f}{:2.6f}{}".format(
            coordinates[CONF_LATITUDE], coordinates[CONF_LONGITUDE], self.type
        )

    @callback
    def data_updated(self, data):
        """Update data."""
        if self._load_data(data) and self.hass:
            self.async_write_ha_state()

    @callback
    def _load_data(self, data):  # noqa: C901
        """Load the sensor with relevant data."""
        # Find sensor

        # Check if we have a new measurement,
        # otherwise we do not have to update the sensor
        if self._measured == data.get(MEASURED):
            return False

        self._attribution = data.get(ATTRIBUTION)
        self._stationname = data.get(STATIONNAME)
        self._measured = data.get(MEASURED)

        if (
            self.type.endswith("_1d")
            or self.type.endswith("_2d")
            or self.type.endswith("_3d")
            or self.type.endswith("_4d")
            or self.type.endswith("_5d")
        ):

            # update forcasting sensors:
            fcday = 0
            if self.type.endswith("_2d"):
                fcday = 1
            if self.type.endswith("_3d"):
                fcday = 2
            if self.type.endswith("_4d"):
                fcday = 3
            if self.type.endswith("_5d"):
                fcday = 4

            # update weather symbol & status text
            if self.type.startswith(SYMBOL) or self.type.startswith(CONDITION):
                try:
                    condition = data.get(FORECAST)[fcday].get(CONDITION)
                except IndexError:
                    _LOGGER.warning("No forecast for fcday=%s", fcday)
                    return False

                if condition:
                    new_state = condition.get(CONDITION)
                    if self.type.startswith(SYMBOL):
                        new_state = condition.get(EXACTNL)
                    if self.type.startswith("conditioncode"):
                        new_state = condition.get(CONDCODE)
                    if self.type.startswith("conditiondetailed"):
                        new_state = condition.get(DETAILED)
                    if self.type.startswith("conditionexact"):
                        new_state = condition.get(EXACT)

                    img = condition.get(IMAGE)

                    if new_state != self._state or img != self._entity_picture:
                        self._state = new_state
                        self._entity_picture = img
                        return True
                return False

            if self.type.startswith(WINDSPEED):
                # hass wants windspeeds in km/h not m/s, so convert:
                try:
                    self._state = data.get(FORECAST)[fcday].get(self.type[:-3])
                    if self._state is not None:
                        self._state = round(self._state * 3.6, 1)
                    return True
                except IndexError:
                    _LOGGER.warning("No forecast for fcday=%s", fcday)
                    return False

            # update all other sensors
            try:
                self._state = data.get(FORECAST)[fcday].get(self.type[:-3])
                return True
            except IndexError:
                _LOGGER.warning("No forecast for fcday=%s", fcday)
                return False

        if self.type == SYMBOL or self.type.startswith(CONDITION):
            # update weather symbol & status text
            condition = data.get(CONDITION)
            if condition:
                if self.type == SYMBOL:
                    new_state = condition.get(EXACTNL)
                if self.type == CONDITION:
                    new_state = condition.get(CONDITION)
                if self.type == "conditioncode":
                    new_state = condition.get(CONDCODE)
                if self.type == "conditiondetailed":
                    new_state = condition.get(DETAILED)
                if self.type == "conditionexact":
                    new_state = condition.get(EXACT)

                img = condition.get(IMAGE)

                if new_state != self._state or img != self._entity_picture:
                    self._state = new_state
                    self._entity_picture = img
                    return True

            return False

        if self.type.startswith(PRECIPITATION_FORECAST):
            # update nested precipitation forecast sensors
            nested = data.get(PRECIPITATION_FORECAST)
            self._timeframe = nested.get(TIMEFRAME)
            self._state = nested.get(self.type[len(PRECIPITATION_FORECAST) + 1 :])
            return True

        if self.type in [WINDSPEED, WINDGUST]:
            # hass wants windspeeds in km/h not m/s, so convert:
            self._state = data.get(self.type)
            if self._state is not None:
                self._state = round(data.get(self.type) * 3.6, 1)
            return True

        if self.type == VISIBILITY:
            # hass wants visibility in km (not m), so convert:
            self._state = data.get(self.type)
            if self._state is not None:
                self._state = round(self._state / 1000, 1)
            return True

        # update all other sensors
        self._state = data.get(self.type)
        return True

    @property
    def attribution(self):
        """Return the attribution."""
        return self._attribution

    @property
    def unique_id(self):
        """Return the unique id."""
        return self._unique_id

    @property
    def name(self):
        """Return the name of the sensor."""
        return f"{self.client_name} {self._name}"

    @property
    def state(self):
        """Return the state of the device."""
        return self._state

    @property
    def should_poll(self):
        """No polling needed."""
        return False

    @property
    def entity_picture(self):
        """Weather symbol if type is symbol."""
        return self._entity_picture

    @property
    def extra_state_attributes(self):
        """Return the state attributes."""
        if self.type.startswith(PRECIPITATION_FORECAST):
            result = {ATTR_ATTRIBUTION: self._attribution}
            if self._timeframe is not None:
                result[TIMEFRAME_LABEL] = "%d min" % (self._timeframe)

            return result

        result = {
            ATTR_ATTRIBUTION: self._attribution,
            SENSOR_TYPES["stationname"][0]: self._stationname,
        }
        if self._measured is not None:
            # convert datetime (Europe/Amsterdam) into local datetime
            local_dt = dt_util.as_local(self._measured)
            result[MEASURED_LABEL] = local_dt.strftime("%c")

        return result

    @property
    def unit_of_measurement(self):
        """Return the unit of measurement of this entity, if any."""
        return self._unit_of_measurement

    @property
    def icon(self):
        """Return possible sensor specific icon."""
        return SENSOR_TYPES[self.type][2]

    @property
    def force_update(self):
        """Return true for continuous sensors, false for discrete sensors."""
        return self._force_update

    @property
    def entity_registry_enabled_default(self) -> bool:
        """Return if the entity should be enabled when first added to the entity registry."""
        return False
