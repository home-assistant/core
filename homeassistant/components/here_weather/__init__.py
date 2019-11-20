"""The here_weather component."""
from datetime import timedelta
import logging

import herepy

from homeassistant.const import CONF_UNIT_SYSTEM_METRIC
from homeassistant.util import Throttle

_LOGGER = logging.getLogger(__name__)

MIN_TIME_BETWEEN_UPDATES = timedelta(seconds=120)


class HEREWeatherData:
    """Get the latest data from HERE."""

    def __init__(
        self,
        here_client: herepy.DestinationWeatherApi,
        mode: str,
        units: str,
        latitude: str = None,
        longitude: str = None,
        location_name: str = None,
        zip_code: str = None,
    ) -> None:
        """Initialize the data object."""
        self.here_client = here_client
        self.latitude = latitude
        self.longitude = longitude
        self.location_name = location_name
        self.zip_code = zip_code
        self.weather_product_type = herepy.WeatherProductType[mode]
        self.units = units
        self.data = None

    @Throttle(MIN_TIME_BETWEEN_UPDATES)
    def update(self) -> None:
        """Get the latest data from HERE."""
        is_metric = convert_units_to_boolean(self.units)
        try:
            if self.zip_code is not None:
                data = self.here_client.weather_for_zip_code(
                    self.zip_code, self.weather_product_type, metric=is_metric
                )
            elif self.location_name is not None:
                data = self.here_client.weather_for_location_name(
                    self.location_name, self.weather_product_type, metric=is_metric
                )
            else:
                data = self.here_client.weather_for_coordinates(
                    self.latitude,
                    self.longitude,
                    self.weather_product_type,
                    metric=is_metric,
                )
            self.data = extract_data_from_payload_for_product_type(
                data, self.weather_product_type
            )
        except herepy.InvalidRequestError as error:
            _LOGGER.error("Error during sensor update: %s", error.message)


def get_attribute_from_here_data(
    here_data: list, attribute_name: str, sensor_number: int = 0
) -> str:
    """Extract and convert data from HERE response or None if not found."""
    if here_data is None:
        return None
    try:
        state = here_data[sensor_number][attribute_name]
        state = convert_asterisk_to_none(state)
        return state
    except KeyError:
        return None


def convert_asterisk_to_none(state: str) -> str:
    """Convert HERE API representation of None."""
    if state == "*":
        state = None
    return state


def convert_units_to_boolean(units: str) -> bool:
    """Convert metric/imperial to true/false."""
    return bool(units == CONF_UNIT_SYSTEM_METRIC)


def extract_data_from_payload_for_product_type(
    data: herepy.DestinationWeatherResponse, product_type: herepy.WeatherProductType
) -> list:
    """Extract the actual data from the HERE payload."""
    if product_type == herepy.WeatherProductType.forecast_astronomy:
        return data.astronomy["astronomy"]
    if product_type == herepy.WeatherProductType.observation:
        return data.observations["location"][0]["observation"]
    if product_type == herepy.WeatherProductType.forecast_7days:
        return data.forecasts["forecastLocation"]["forecast"]
    if product_type == herepy.WeatherProductType.forecast_7days_simple:
        return data.dailyForecasts["forecastLocation"]["forecast"]
    if product_type == herepy.WeatherProductType.forecast_hourly:
        return data.hourlyForecasts["forecastLocation"]["forecast"]


def convert_unit_of_measurement_if_needed(unit_system, unit_of_measurement: str) -> str:
    """Convert the unit of measurement to imperial if configured."""
    if unit_system != CONF_UNIT_SYSTEM_METRIC:
        if unit_of_measurement == "°C":
            unit_of_measurement = "°F"
        elif unit_of_measurement == "cm":
            unit_of_measurement = "in"
        elif unit_of_measurement == "km/h":
            unit_of_measurement = "mph"
        elif unit_of_measurement == "mbar":
            unit_of_measurement = "in"
        elif unit_of_measurement == "km":
            unit_of_measurement = "mi"
    return unit_of_measurement
