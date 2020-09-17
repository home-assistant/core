"""Constants for here_weather tests."""
import json

import herepy

from tests.common import load_fixture

daily_simple_forecasts_response = herepy.DestinationWeatherResponse.new_from_jsondict(
    json.loads(load_fixture("here_weather/daily_simple_forecasts.json")),
    param_defaults={"dailyForecasts": None},
)

astronomy_response = herepy.DestinationWeatherResponse.new_from_jsondict(
    json.loads(load_fixture("here_weather/astronomy.json")),
    param_defaults={"astronomy": None},
)

hourly_response = herepy.DestinationWeatherResponse.new_from_jsondict(
    json.loads(load_fixture("here_weather/hourly.json")),
    param_defaults={"hourlyForecasts": None},
)

observation_response = herepy.DestinationWeatherResponse.new_from_jsondict(
    json.loads(load_fixture("here_weather/observation.json")),
    param_defaults={"observations": None},
)

daily_response = herepy.DestinationWeatherResponse.new_from_jsondict(
    json.loads(load_fixture("here_weather/daily.json")),
    param_defaults={"forecasts": None},
)
