"""Configure py.test."""
import json
from unittest.mock import patch

import pytest

from tests.common import load_fixture


@pytest.fixture(name="tomorrowio_config_flow_connect", autouse=True)
def tomorrowio_config_flow_connect():
    """Mock valid tomorrowio config flow setup."""
    with patch(
        "homeassistant.components.tomorrowio.config_flow.TomorrowioV4.realtime",
        return_value={},
    ):
        yield


@pytest.fixture(name="tomorrowio_config_entry_update", autouse=True)
def tomorrowio_config_entry_update_fixture():
    """Mock valid tomorrowio config entry setup."""
    with patch(
        "homeassistant.components.tomorrowio.TomorrowioV4.realtime_and_all_forecasts",
        return_value=json.loads(load_fixture("v4.json", "tomorrowio")),
    ):
        yield


@pytest.fixture(name="climacell_config_entry_update")
def climacell_config_entry_update_fixture():
    """Mock valid climacell config entry setup."""
    with patch(
        "homeassistant.components.climacell.ClimaCellV3.realtime",
        return_value={},
    ), patch(
        "homeassistant.components.climacell.ClimaCellV3.forecast_hourly",
        return_value={},
    ), patch(
        "homeassistant.components.climacell.ClimaCellV3.forecast_daily",
        return_value={},
    ), patch(
        "homeassistant.components.climacell.ClimaCellV3.forecast_nowcast",
        return_value={},
    ):
        yield
