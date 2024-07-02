"""Support for displaying weather info from Ecobee API."""

from __future__ import annotations

from datetime import timedelta

from pyecobee.const import ECOBEE_STATE_UNKNOWN

from homeassistant.components.weather import (
    ATTR_FORECAST_CONDITION,
    ATTR_FORECAST_NATIVE_TEMP,
    ATTR_FORECAST_NATIVE_TEMP_LOW,
    ATTR_FORECAST_NATIVE_WIND_SPEED,
    ATTR_FORECAST_TIME,
    ATTR_FORECAST_WIND_BEARING,
    Forecast,
    WeatherEntity,
    WeatherEntityFeature,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    UnitOfLength,
    UnitOfPressure,
    UnitOfSpeed,
    UnitOfTemperature,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.util import dt as dt_util

from .const import (
    DOMAIN,
    ECOBEE_MODEL_TO_NAME,
    ECOBEE_WEATHER_SYMBOL_TO_HASS,
    MANUFACTURER,
)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
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

    _attr_native_pressure_unit = UnitOfPressure.HPA
    _attr_native_temperature_unit = UnitOfTemperature.FAHRENHEIT
    _attr_native_visibility_unit = UnitOfLength.METERS
    _attr_native_wind_speed_unit = UnitOfSpeed.MILES_PER_HOUR
    _attr_has_entity_name = True
    _attr_name = None
    _attr_supported_features = WeatherEntityFeature.FORECAST_DAILY

    def __init__(self, data, name, index):
        """Initialize the Ecobee weather platform."""
        self.data = data
        self._name = name
        self._index = index
        self.weather = None
        self._attr_unique_id = data.ecobee.get_thermostat(self._index)["identifier"]

    def get_forecast(self, index, param):
        """Retrieve forecast parameter."""
        try:
            forecast = self.weather["forecasts"][index]
            return forecast[param]
        except (IndexError, KeyError) as err:
            raise ValueError from err

    @property
    def device_info(self) -> DeviceInfo:
        """Return device information for the ecobee weather platform."""
        thermostat = self.data.ecobee.get_thermostat(self._index)
        model: str | None
        try:
            model = f"{ECOBEE_MODEL_TO_NAME[thermostat['modelNumber']]} Thermostat"
        except KeyError:
            # Ecobee model is not in our list
            model = None

        return DeviceInfo(
            identifiers={(DOMAIN, thermostat["identifier"])},
            manufacturer=MANUFACTURER,
            model=model,
            name=self._name,
        )

    @property
    def condition(self):
        """Return the current condition."""
        try:
            return ECOBEE_WEATHER_SYMBOL_TO_HASS[self.get_forecast(0, "weatherSymbol")]
        except ValueError:
            return None

    @property
    def native_temperature(self):
        """Return the temperature."""
        try:
            return float(self.get_forecast(0, "temperature")) / 10
        except ValueError:
            return None

    @property
    def native_pressure(self):
        """Return the pressure."""
        try:
            pressure = self.get_forecast(0, "pressure")
            return round(pressure)
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
    def native_visibility(self):
        """Return the visibility."""
        try:
            return int(self.get_forecast(0, "visibility"))
        except ValueError:
            return None

    @property
    def native_wind_speed(self):
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

    def _forecast(self) -> list[Forecast] | None:
        """Return the forecast array."""
        if "forecasts" not in self.weather:
            return None

        forecasts: list[Forecast] = []
        date = dt_util.utcnow()
        for day in range(5):
            forecast = _process_forecast(self.weather["forecasts"][day])
            if forecast is None:
                continue
            forecast[ATTR_FORECAST_TIME] = date.isoformat()
            date += timedelta(days=1)
            forecasts.append(forecast)

        if forecasts:
            return forecasts
        return None

    async def async_forecast_daily(self) -> list[Forecast] | None:
        """Return the daily forecast in native units."""
        return self._forecast()

    async def async_update(self) -> None:
        """Get the latest weather data."""
        await self.data.update()
        thermostat = self.data.ecobee.get_thermostat(self._index)
        self.weather = thermostat.get("weather")
        await self.async_update_listeners(("daily",))


def _process_forecast(json):
    """Process a single ecobee API forecast to return expected values."""
    forecast = {}
    try:
        forecast[ATTR_FORECAST_CONDITION] = ECOBEE_WEATHER_SYMBOL_TO_HASS[
            json["weatherSymbol"]
        ]
        if json["tempHigh"] != ECOBEE_STATE_UNKNOWN:
            forecast[ATTR_FORECAST_NATIVE_TEMP] = float(json["tempHigh"]) / 10
        if json["tempLow"] != ECOBEE_STATE_UNKNOWN:
            forecast[ATTR_FORECAST_NATIVE_TEMP_LOW] = float(json["tempLow"]) / 10
        if json["windBearing"] != ECOBEE_STATE_UNKNOWN:
            forecast[ATTR_FORECAST_WIND_BEARING] = int(json["windBearing"])
        if json["windSpeed"] != ECOBEE_STATE_UNKNOWN:
            forecast[ATTR_FORECAST_NATIVE_WIND_SPEED] = int(json["windSpeed"])

    except (ValueError, IndexError, KeyError):
        return None

    if forecast:
        return forecast
    return None
