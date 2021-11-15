"""Configure py.test."""
import json
from unittest.mock import patch

import pytest

from tests.common import load_fixture


@pytest.fixture(name="climacell_config_entry_update")
def climacell_config_entry_update_fixture():
    """Mock valid climacell config entry setup."""
    with patch(
        "homeassistant.components.climacell.ClimaCellV3.realtime",
        return_value=json.loads(load_fixture("climacell/v3_realtime.json")),
    ), patch(
        "homeassistant.components.climacell.ClimaCellV3.forecast_hourly",
        return_value=json.loads(load_fixture("climacell/v3_forecast_hourly.json")),
    ), patch(
        "homeassistant.components.climacell.ClimaCellV3.forecast_daily",
        return_value=json.loads(load_fixture("climacell/v3_forecast_daily.json")),
    ), patch(
        "homeassistant.components.climacell.ClimaCellV3.forecast_nowcast",
        return_value=json.loads(load_fixture("climacell/v3_forecast_nowcast.json")),
    ), patch(
        "homeassistant.components.climacell.ClimaCellV4.realtime_and_all_forecasts",
        return_value=json.loads(load_fixture("climacell/v4.json")),
    ):
        yield
