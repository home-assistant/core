"""Support for displaying weather info from Ecobee API."""
from datetime import timedelta

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
from homeassistant.const import PRESSURE_HPA, PRESSURE_INHG, TEMP_FAHRENHEIT
from homeassistant.util import dt as dt_util
from homeassistant.util.pressure import convert as pressure_convert

from .const import (
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

    _attr_temperature_unit = TEMP_FAHRENHEIT

    def __init__(self, data, name, index):
        """Initialize the Ecobee weather platform."""
        self.data = data
        self._attr_name = name
        self._index = index
        self.weather = None
        thermostat = self.data.ecobee.get_thermostat(self._index)
        self._attr_unique_id = thermostat["identifier"]
        self._attr_device_info = {
            "identifiers": {(DOMAIN, thermostat["identifier"])},
            "name": self._attr_name,
            "manufacturer": MANUFACTURER,
            "model": f"{ECOBEE_MODEL_TO_NAME.get(thermostat['modelNumber'])} Thermostat",
        }

    def get_forecast(self, index, param):
        """Retrieve forecast parameter."""
        try:
            forecast = self.weather["forecasts"][index]
            return forecast[param]
        except (IndexError, KeyError) as err:
            raise ValueError from err

    async def async_update(self):
        """Get the latest weather data."""
        await self.data.update()
        thermostat = self.data.ecobee.get_thermostat(self._index)
        self.weather = thermostat.get("weather")
        self._attr_condition = ECOBEE_WEATHER_SYMBOL_TO_HASS.get(
            self.get_forecast(0, "weatherSymbol")
        )
        try:
            self._attr_temperature = float(self.get_forecast(0, "temperature")) / 10
        except ValueError:
            self._attr_temperature = None
        try:
            pressure = self.get_forecast(0, "pressure")
            if not self.hass.config.units.is_metric:
                pressure = pressure_convert(pressure, PRESSURE_HPA, PRESSURE_INHG)
                self._attr_pressure = round(pressure, 2)
            else:
                self._attr_pressure = round(pressure)
        except ValueError:
            self._attr_pressure = None
        try:
            self._attr_humidity = int(self.get_forecast(0, "relativeHumidity"))
        except ValueError:
            self._attr_humidity = None
        try:
            self._attr_visibility = int(self.get_forecast(0, "visibility")) / 1000
        except ValueError:
            self._attr_visibility = None
        try:
            self._attr_wind_speed = int(self.get_forecast(0, "windSpeed"))
        except ValueError:
            self._attr_wind_speed = None
        try:
            self._attr_wind_bearing = int(self.get_forecast(0, "windBearing"))
        except ValueError:
            self._attr_wind_bearing = None
        if self.weather:
            self._attr_attribution = f"Ecobee weather provided by {self.weather.get('weatherStation', 'UNKNOWN')} at {self.weather.get('timestamp', 'UNKNOWN')} UTC"
        else:
            self._attr_attribution = None
        if "forecasts" not in self.weather:
            self._attr_forecast = None
        else:
            forecasts = []
            date = dt_util.utcnow()
            for day in range(0, 5):
                forecast = _process_forecast(self.weather["forecasts"][day])
                if forecast is None:
                    continue
                forecast[ATTR_FORECAST_TIME] = date.isoformat()
                date += timedelta(days=1)
                forecasts.append(forecast)
            self._attr_forecast = forecasts if forecasts else None


def _process_forecast(json):
    """Process a single ecobee API forecast to return expected values."""
    forecast = {}
    try:
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
