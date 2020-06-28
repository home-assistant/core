"""Support for displaying weather info from Ecobee API."""
from datetime import datetime

from pyecobee.const import ECOBEE_STATE_UNKNOWN

from homeassistant.components.weather import (
    ATTR_FORECAST_CONDITION,
    ATTR_FORECAST_TEMP,
    ATTR_FORECAST_TEMP_LOW,
    ATTR_FORECAST_TIME,
    ATTR_FORECAST_WIND_BEARING,
    ATTR_FORECAST_WIND_SPEED,
    WeatherEntity,
)
from homeassistant.const import TEMP_FAHRENHEIT

from .const import (
    _LOGGER,
    DOMAIN,
    ECOBEE_MODEL_TO_NAME,
    ECOBEE_WEATHER_SYMBOL_TO_HASS,
    MANUFACTURER,
)


async def async_setup_entry(hass, config_entry, async_add_entities):
    """Set up the ecobee weather platform."""
    data = hass.data[DOMAIN]
    dev = []
    for index in range(len(data.ecobee.thermostats)):
        thermostat = data.ecobee.get_thermostat(index)
        if "weather" in thermostat:
            dev.append(EcobeeWeather(data, thermostat["name"], index))

    async_add_entities(dev, True)


class EcobeeWeather(WeatherEntity):
    """Representation of Ecobee weather data."""

    def __init__(self, data, name, index):
        """Initialize the Ecobee weather platform."""
        self.data = data
        self._name = name
        self._index = index
        self.weather = None

    def get_forecast(self, index, param):
        """Retrieve forecast parameter."""
        try:
            forecast = self.weather["forecasts"][index]
            return forecast[param]
        except (ValueError, IndexError, KeyError):
            raise ValueError

    @property
    def name(self):
        """Return the name of the sensor."""
        return self._name

    @property
    def unique_id(self):
        """Return a unique identifier for the weather platform."""
        return self.data.ecobee.get_thermostat(self._index)["identifier"]

    @property
    def device_info(self):
        """Return device information for the ecobee weather platform."""
        thermostat = self.data.ecobee.get_thermostat(self._index)
        try:
            model = f"{ECOBEE_MODEL_TO_NAME[thermostat['modelNumber']]} Thermostat"
        except KeyError:
            _LOGGER.error(
                "Model number for ecobee thermostat %s not recognized. "
                "Please visit this link and provide the following information: "
                "https://github.com/home-assistant/home-assistant/issues/27172 "
                "Unrecognized model number: %s",
                thermostat["name"],
                thermostat["modelNumber"],
            )
            return None

        return {
            "identifiers": {(DOMAIN, thermostat["identifier"])},
            "name": self.name,
            "manufacturer": MANUFACTURER,
            "model": model,
        }

    @property
    def condition(self):
        """Return the current condition."""
        try:
            return ECOBEE_WEATHER_SYMBOL_TO_HASS[self.get_forecast(0, "weatherSymbol")]
        except ValueError:
            return None

    @property
    def temperature(self):
        """Return the temperature."""
        try:
            return float(self.get_forecast(0, "temperature")) / 10
        except ValueError:
            return None

    @property
    def temperature_unit(self):
        """Return the unit of measurement."""
        return TEMP_FAHRENHEIT

    @property
    def pressure(self):
        """Return the pressure."""
        try:
            return int(self.get_forecast(0, "pressure"))
        except ValueError:
            return None

    @property
    def humidity(self):
        """Return the humidity."""
        try:
            return int(self.get_forecast(0, "relativeHumidity"))
        except ValueError:
            return None

    @property
    def visibility(self):
        """Return the visibility."""
        try:
            return int(self.get_forecast(0, "visibility")) / 1000
        except ValueError:
            return None

    @property
    def wind_speed(self):
        """Return the wind speed."""
        try:
            return int(self.get_forecast(0, "windSpeed"))
        except ValueError:
            return None

    @property
    def wind_bearing(self):
        """Return the wind direction."""
        try:
            return int(self.get_forecast(0, "windBearing"))
        except ValueError:
            return None

    @property
    def attribution(self):
        """Return the attribution."""
        if not self.weather:
            return None

        station = self.weather.get("weatherStation", "UNKNOWN")
        time = self.weather.get("timestamp", "UNKNOWN")
        return f"Ecobee weather provided by {station} at {time} UTC"

    @property
    def forecast(self):
        """Return the forecast array."""
        if "forecasts" not in self.weather:
            return None

        forecasts = []
        for day in range(1, 5):
            forecast = _process_forecast(self.weather["forecasts"][day])
            if forecast is None:
                continue
            forecasts.append(forecast)

        if forecasts:
            return forecasts
        return None

    async def async_update(self):
        """Get the latest weather data."""
        await self.data.update()
        thermostat = self.data.ecobee.get_thermostat(self._index)
        self.weather = thermostat.get("weather")


def _process_forecast(json):
    """Process a single ecobee API forecast to return expected values."""
    forecast = {}
    try:
        forecast[ATTR_FORECAST_TIME] = datetime.strptime(
            json["dateTime"], "%Y-%m-%d %H:%M:%S"
        ).isoformat()
        forecast[ATTR_FORECAST_CONDITION] = ECOBEE_WEATHER_SYMBOL_TO_HASS[
            json["weatherSymbol"]
        ]
        if json["tempHigh"] != ECOBEE_STATE_UNKNOWN:
            forecast[ATTR_FORECAST_TEMP] = float(json["tempHigh"]) / 10
        if json["tempLow"] != ECOBEE_STATE_UNKNOWN:
            forecast[ATTR_FORECAST_TEMP_LOW] = float(json["tempLow"]) / 10
        if json["windBearing"] != ECOBEE_STATE_UNKNOWN:
            forecast[ATTR_FORECAST_WIND_BEARING] = int(json["windBearing"])
        if json["windSpeed"] != ECOBEE_STATE_UNKNOWN:
            forecast[ATTR_FORECAST_WIND_SPEED] = int(json["windSpeed"])

    except (ValueError, IndexError, KeyError):
        return None

    if forecast:
        return forecast
    return None
