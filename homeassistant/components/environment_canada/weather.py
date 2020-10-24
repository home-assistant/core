"""Platform for retrieving meteorological data from Environment Canada."""
import datetime
import re

from env_canada import ECData  # pylint: disable=import-error
import voluptuous as vol

from homeassistant.components.weather import (
    ATTR_FORECAST_CONDITION,
    ATTR_FORECAST_PRECIPITATION_PROBABILITY,
    ATTR_FORECAST_TEMP,
    ATTR_FORECAST_TEMP_LOW,
    ATTR_FORECAST_TIME,
    PLATFORM_SCHEMA,
    WeatherEntity,
)
from homeassistant.const import CONF_LATITUDE, CONF_LONGITUDE, CONF_NAME, TEMP_CELSIUS
import homeassistant.helpers.config_validation as cv
import homeassistant.util.dt as dt

CONF_FORECAST = "forecast"
CONF_ATTRIBUTION = "Data provided by Environment Canada"
CONF_STATION = "station"


def validate_station(station):
    """Check that the station ID is well-formed."""
    if station is None:
        return
    if not re.fullmatch(r"[A-Z]{2}/s0000\d{3}", station):
        raise vol.error.Invalid('Station ID must be of the form "XX/s0000###"')
    return station


PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {
        vol.Optional(CONF_NAME): cv.string,
        vol.Optional(CONF_STATION): validate_station,
        vol.Inclusive(CONF_LATITUDE, "latlon"): cv.latitude,
        vol.Inclusive(CONF_LONGITUDE, "latlon"): cv.longitude,
        vol.Optional(CONF_FORECAST, default="daily"): vol.In(["daily", "hourly"]),
    }
)

# Icon codes from http://dd.weatheroffice.ec.gc.ca/citypage_weather/
# docs/current_conditions_icon_code_descriptions_e.csv
ICON_CONDITION_MAP = {
    "sunny": [0, 1],
    "clear-night": [30, 31],
    "partlycloudy": [2, 3, 4, 5, 22, 32, 33, 34, 35],
    "cloudy": [10],
    "rainy": [6, 9, 11, 12, 28, 36],
    "lightning-rainy": [19, 39, 46, 47],
    "pouring": [13],
    "snowy-rainy": [7, 14, 15, 27, 37],
    "snowy": [8, 16, 17, 18, 25, 26, 38, 40],
    "windy": [43],
    "fog": [20, 21, 23, 24, 44],
    "hail": [26, 27],
}


def setup_platform(hass, config, add_devices, discovery_info=None):
    """Set up the Environment Canada weather."""
    if config.get(CONF_STATION):
        ec_data = ECData(station_id=config[CONF_STATION])
    else:
        lat = config.get(CONF_LATITUDE, hass.config.latitude)
        lon = config.get(CONF_LONGITUDE, hass.config.longitude)
        ec_data = ECData(coordinates=(lat, lon))

    add_devices([ECWeather(ec_data, config)])


class ECWeather(WeatherEntity):
    """Representation of a weather condition."""

    def __init__(self, ec_data, config):
        """Initialize Environment Canada weather."""
        self.ec_data = ec_data
        self.platform_name = config.get(CONF_NAME)
        self.forecast_type = config[CONF_FORECAST]

    @property
    def attribution(self):
        """Return the attribution."""
        return CONF_ATTRIBUTION

    @property
    def name(self):
        """Return the name of the weather entity."""
        if self.platform_name:
            return self.platform_name
        return self.ec_data.metadata.get("location")

    @property
    def temperature(self):
        """Return the temperature."""
        if self.ec_data.conditions.get("temperature", {}).get("value"):
            return float(self.ec_data.conditions["temperature"]["value"])
        if self.ec_data.hourly_forecasts[0].get("temperature"):
            return float(self.ec_data.hourly_forecasts[0]["temperature"])
        return None

    @property
    def temperature_unit(self):
        """Return the unit of measurement."""
        return TEMP_CELSIUS

    @property
    def humidity(self):
        """Return the humidity."""
        if self.ec_data.conditions.get("humidity", {}).get("value"):
            return float(self.ec_data.conditions["humidity"]["value"])
        return None

    @property
    def wind_speed(self):
        """Return the wind speed."""
        if self.ec_data.conditions.get("wind_speed", {}).get("value"):
            return float(self.ec_data.conditions["wind_speed"]["value"])
        return None

    @property
    def wind_bearing(self):
        """Return the wind bearing."""
        if self.ec_data.conditions.get("wind_bearing", {}).get("value"):
            return float(self.ec_data.conditions["wind_bearing"]["value"])
        return None

    @property
    def pressure(self):
        """Return the pressure."""
        if self.ec_data.conditions.get("pressure", {}).get("value"):
            return 10 * float(self.ec_data.conditions["pressure"]["value"])
        return None

    @property
    def visibility(self):
        """Return the visibility."""
        if self.ec_data.conditions.get("visibility", {}).get("value"):
            return float(self.ec_data.conditions["visibility"]["value"])
        return None

    @property
    def condition(self):
        """Return the weather condition."""
        icon_code = None

        if self.ec_data.conditions.get("icon_code", {}).get("value"):
            icon_code = self.ec_data.conditions["icon_code"]["value"]
        elif self.ec_data.hourly_forecasts[0].get("icon_code"):
            icon_code = self.ec_data.hourly_forecasts[0]["icon_code"]

        if icon_code:
            return icon_code_to_condition(int(icon_code))
        return ""

    @property
    def forecast(self):
        """Return the forecast array."""
        return get_forecast(self.ec_data, self.forecast_type)

    def update(self):
        """Get the latest data from Environment Canada."""
        self.ec_data.update()


def get_forecast(ec_data, forecast_type):
    """Build the forecast array."""
    forecast_array = []

    if forecast_type == "daily":
        half_days = ec_data.daily_forecasts
        if half_days[0]["temperature_class"] == "high":
            forecast_array.append(
                {
                    ATTR_FORECAST_TIME: dt.now().isoformat(),
                    ATTR_FORECAST_TEMP: int(half_days[0]["temperature"]),
                    ATTR_FORECAST_TEMP_LOW: int(half_days[1]["temperature"]),
                    ATTR_FORECAST_CONDITION: icon_code_to_condition(
                        int(half_days[0]["icon_code"])
                    ),
                    ATTR_FORECAST_PRECIPITATION_PROBABILITY: int(
                        half_days[0]["precip_probability"]
                    ),
                }
            )
            half_days = half_days[2:]
        else:
            half_days = half_days[1:]

        for day, high, low in zip(range(1, 6), range(0, 9, 2), range(1, 10, 2)):
            forecast_array.append(
                {
                    ATTR_FORECAST_TIME: (
                        dt.now() + datetime.timedelta(days=day)
                    ).isoformat(),
                    ATTR_FORECAST_TEMP: int(half_days[high]["temperature"]),
                    ATTR_FORECAST_TEMP_LOW: int(half_days[low]["temperature"]),
                    ATTR_FORECAST_CONDITION: icon_code_to_condition(
                        int(half_days[high]["icon_code"])
                    ),
                    ATTR_FORECAST_PRECIPITATION_PROBABILITY: int(
                        half_days[high]["precip_probability"]
                    ),
                }
            )

    elif forecast_type == "hourly":
        hours = ec_data.hourly_forecasts
        for hour in range(0, 24):
            forecast_array.append(
                {
                    ATTR_FORECAST_TIME: dt.as_local(
                        datetime.datetime.strptime(hours[hour]["period"], "%Y%m%d%H%M")
                    ).isoformat(),
                    ATTR_FORECAST_TEMP: int(hours[hour]["temperature"]),
                    ATTR_FORECAST_CONDITION: icon_code_to_condition(
                        int(hours[hour]["icon_code"])
                    ),
                    ATTR_FORECAST_PRECIPITATION_PROBABILITY: int(
                        hours[hour]["precip_probability"]
                    ),
                }
            )

    return forecast_array


def icon_code_to_condition(icon_code):
    """Return the condition corresponding to an icon code."""
    for condition, codes in ICON_CONDITION_MAP.items():
        if icon_code in codes:
            return condition
    return None
