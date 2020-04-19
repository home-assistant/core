"""The FMI (Finnish Meteorological Institute) component."""

from datetime import date, timedelta
import logging

from dateutil import tz
import fmi_weather_client as fmi
from fmi_weather_client.errors import ClientError, ServerError
import voluptuous as vol

import homeassistant.components.sun as sun
from homeassistant.const import CONF_LATITUDE, CONF_LONGITUDE, CONF_NAME, CONF_OFFSET
import homeassistant.helpers.config_validation as cv
from homeassistant.util import Throttle

_LOGGER = logging.getLogger(__name__)

CONF_MIN_HUMIDITY = "min_relative_humidity"
CONF_MAX_HUMIDITY = "max_relative_humidity"
CONF_MIN_TEMP = "min_temperature"
CONF_MAX_TEMP = "max_temperature"
CONF_MIN_WIND_SPEED = "min_wind_speed"
CONF_MAX_WIND_SPEED = "max_wind_speed"
CONF_MIN_PRECIPITATION = "min_precipitation"
CONF_MAX_PRECIPITATION = "max_precipitation"

DOMAIN = "fmi"

MIN_TIME_BETWEEN_UPDATES = timedelta(minutes=15)

HUMIDITY_RANGE = list(range(1, 101))
TEMP_RANGE = list(range(-40, 50))
WIND_SPEED = list(range(0, 31))
FORECAST_OFFSET = [0, 1, 2, 3, 4, 6, 8, 12, 24]  # Based on API test runs
DEFAULT_NAME = "FMI"

BEST_COND_SYMBOLS = [1, 2, 21, 3, 31, 32, 41, 42, 51, 52, 91, 92]

BEST_CONDITION_AVAIL = "available"
BEST_CONDITION_NOT_AVAIL = "not_available"

ATTRIBUTION = "Weather Data provided by FMI"

# FMI Weather Visibility Constants
FMI_WEATHER_SYMBOL_MAP = {
    0: "clear-night",  # custom value 0 - not defined by FMI
    1: "sunny",  # "Clear",
    2: "partlycloudy",  # "Partially Clear",
    21: "rainy",  # "Light Showers",
    22: "pouring",  # "Showers",
    23: "pouring",  # "Strong Rain Showers",
    3: "cloudy",  # "Cloudy",
    31: "rainy",  # "Weak rains",
    32: "rainy",  # "Rains",
    33: "pouring",  # "Heavy Rains",
    41: "snowy-rainy",  # "Weak Snow",
    42: "cloudy",  # "Cloudy",
    43: "snowy",  # "Strong Snow",
    51: "snowy",  # "Light Snow",
    52: "snowy",  # "Snow",
    53: "snowy",  # "Heavy Snow",
    61: "lightning",  # "Thunderstorms",
    62: "lightning-rainy",  # "Strong Thunderstorms",
    63: "lightning",  # "Thunderstorms",
    64: "lightning-rainy",  # "Strong Thunderstorms",
    71: "rainy",  # "Weak Sleet",
    72: "rainy",  # "Sleet",
    73: "pouring",  # "Heavy Sleet",
    81: "rainy",  # "Light Sleet",
    82: "rainy",  # "Sleet",
    83: "pouring",  # "Heavy Sleet",
    91: "fog",  # "Fog",
    92: "fog",  # "Fog"
}

CONFIG_SCHEMA = vol.Schema(
    {
        DOMAIN: vol.Schema(
            {
                vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
                vol.Inclusive(
                    CONF_LATITUDE,
                    "coordinates",
                    "Latitude and longitude must exist together",
                ): cv.latitude,
                vol.Inclusive(
                    CONF_LONGITUDE,
                    "coordinates",
                    "Latitude and longitude must exist together",
                ): cv.longitude,
                vol.Optional(CONF_OFFSET, default=0): vol.In(FORECAST_OFFSET),
                vol.Optional(CONF_MIN_HUMIDITY, default=30): vol.In(HUMIDITY_RANGE),
                vol.Optional(CONF_MAX_HUMIDITY, default=70): vol.In(HUMIDITY_RANGE),
                vol.Optional(CONF_MIN_TEMP, default=10): vol.In(TEMP_RANGE),
                vol.Optional(CONF_MAX_TEMP, default=30): vol.In(TEMP_RANGE),
                vol.Optional(CONF_MIN_WIND_SPEED, default=0): vol.In(WIND_SPEED),
                vol.Optional(CONF_MAX_WIND_SPEED, default=25): vol.In(WIND_SPEED),
                vol.Optional(CONF_MIN_PRECIPITATION, default=0.0): cv.small_float,
                vol.Optional(CONF_MAX_PRECIPITATION, default=0.2): cv.small_float,
            }
        )
    },
    extra=vol.ALLOW_EXTRA,
)


def setup(hass, config):
    """Set up the FMI Integration."""
    try:
        latitude = config[DOMAIN][CONF_LATITUDE]
        longitude = config[DOMAIN][CONF_LONGITUDE]
    except KeyError:
        if hass.config.latitude is None or hass.config.longitude is None:
            _LOGGER.error(
                "Latitude & longitude not set in Home Assistant config and not provided in configuration as well!!"
            )
            return False

    latitude = hass.config.latitude
    longitude = hass.config.longitude

    try:
        name = config[DOMAIN][CONF_NAME]
        time_step = config[DOMAIN][CONF_OFFSET]
        min_temperature = float(config[DOMAIN][CONF_MIN_TEMP])
        max_temperature = float(config[DOMAIN][CONF_MAX_TEMP])
        min_humidity = float(config[DOMAIN][CONF_MIN_HUMIDITY])
        max_humidity = float(config[DOMAIN][CONF_MAX_HUMIDITY])
        min_wind_speed = float(config[DOMAIN][CONF_MIN_WIND_SPEED])
        max_wind_speed = float(config[DOMAIN][CONF_MAX_WIND_SPEED])
        min_precip = float(config[DOMAIN][CONF_MIN_PRECIPITATION])
        max_precip = float(config[DOMAIN][CONF_MAX_PRECIPITATION])
    except ValueError as v_e:
        _LOGGER.error("Parameter configuration mismatch - %s", v_e)
        return False
    except KeyError as k_e:
        _LOGGER.error("Parameter key not found - %s", k_e)
        return False

    fmi_object = FMI(
        name,
        hass,
        latitude,
        longitude,
        min_temperature,
        max_temperature,
        min_humidity,
        max_humidity,
        min_wind_speed,
        max_wind_speed,
        min_precip,
        max_precip,
        time_step,
    )

    hass.data[DOMAIN] = {"fmi_object": fmi_object}

    hass.async_create_task(
        hass.helpers.discovery.async_load_platform("weather", DOMAIN, {}, config)
    )
    hass.async_create_task(
        hass.helpers.discovery.async_load_platform("sensor", DOMAIN, {}, config)
    )

    return True


def get_weather_symbol(symbol, hass=None):
    """Get a weather symbol for the symbol value."""
    ret_val = ""
    if symbol in FMI_WEATHER_SYMBOL_MAP.keys():
        ret_val = FMI_WEATHER_SYMBOL_MAP[symbol]
        if ret_val == 1 and hass is not None:  # Clear as per FMI
            if hass.states.get("sun.sun") == sun.STATE_BELOW_HORIZON:
                # Clear night
                ret_val = FMI_WEATHER_SYMBOL_MAP[0]
    return ret_val


class FMI:
    """Get the latest data from FMI."""

    def __init__(
        self,
        name,
        hass,
        latitude,
        longitude,
        min_temperature,
        max_temperature,
        min_humidity,
        max_humidity,
        min_wind_speed,
        max_wind_speed,
        min_precip,
        max_precip,
        time_step,
    ):
        """Initialize the data object."""
        # Input parameters
        self.name = name
        self.latitude = latitude
        self.longitude = longitude
        self.time_step = time_step
        self.min_temperature = min_temperature
        self.max_temperature = max_temperature
        self.min_humidity = min_humidity
        self.max_humidity = max_humidity
        self.min_wind_speed = min_wind_speed
        self.max_wind_speed = max_wind_speed
        self.min_precip = min_precip
        self.max_precip = max_precip

        # Updated from FMI API
        self.hourly = None
        self.current = None

        # Best Time Attributes derived based on forecast weather data
        self.best_time = None
        self.best_temperature = None
        self.best_humidity = None
        self.best_wind_speed = None
        self.best_precipitation = None
        self.best_state = None

        # Hass object
        self.hass = hass

    @Throttle(MIN_TIME_BETWEEN_UPDATES)
    def update(self):
        """Get the latest and forecasted weather from FMI."""

        def update_best_weather_condition():
            if self.hourly is None:
                return

            if self.current is None:
                return

            curr_date = date.today()

            # Init values
            self.best_state = BEST_CONDITION_NOT_AVAIL
            self.best_time = self.current.data.time.astimezone(tz.tzlocal())
            self.best_temperature = self.current.data.temperature.value
            self.best_humidity = self.current.data.humidity.value
            self.best_wind_speed = self.current.data.wind_speed.value
            self.best_precipitation = self.current.data.precipitation_amount.value

            for forecast in self.hourly.forecasts:
                local_time = forecast.time.astimezone(tz.tzlocal())

                if local_time.day == curr_date.day + 1:
                    # Tracking best conditions for only this day
                    break

                if (
                    (forecast.symbol.value in BEST_COND_SYMBOLS)
                    and (forecast.wind_speed.value >= self.min_wind_speed)
                    and (forecast.wind_speed.value <= self.max_wind_speed)
                ):
                    if (
                        forecast.temperature.value >= self.min_temperature
                        and forecast.temperature.value <= self.max_temperature
                    ):
                        if (
                            forecast.humidity.value >= self.min_humidity
                            and forecast.humidity.value <= self.max_humidity
                        ):
                            if (
                                forecast.precipitation_amount.value >= self.min_precip
                                and forecast.precipitation_amount.value
                                <= self.max_precip
                            ):
                                # What more can you ask for?
                                # Compare with temperature value already stored and update if necessary
                                self.best_state = BEST_CONDITION_AVAIL

                if self.best_state is BEST_CONDITION_AVAIL:
                    if forecast.temperature.value > self.best_temperature:
                        self.best_time = local_time
                        self.best_temperature = forecast.temperature.value
                        self.best_humidity = forecast.humidity.value
                        self.best_wind_speed = forecast.wind_speed.value
                        self.best_precipitation = forecast.precipitation_amount.value

        # Current Weather
        try:
            self.current = fmi.weather_by_coordinates(self.latitude, self.longitude)

        except ClientError as err:
            err_string = (
                "Client error with status "
                + str(err.status_code)
                + " and message "
                + err.message
            )
            _LOGGER.error(err_string)
        except ServerError as err:
            err_string = (
                "Server error with status "
                + str(err.status_code)
                + " and message "
                + err.body
            )
            _LOGGER.error(err_string)
            self.current = None

        # Hourly weather for 24hrs.
        try:
            self.hourly = fmi.forecast_by_coordinates(
                self.latitude, self.longitude, timestep_hours=self.time_step
            )

        except ClientError as err:
            err_string = (
                "Client error with status "
                + str(err.status_code)
                + " and message "
                + err.message
            )
            _LOGGER.error(err_string)
        except ServerError as err:
            err_string = (
                "Server error with status "
                + str(err.status_code)
                + " and message "
                + err.body
            )
            _LOGGER.error(err_string)
            self.hourly = None

        # Update best time parameters
        update_best_weather_condition()
