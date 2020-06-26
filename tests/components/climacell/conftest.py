"""Configure py.test."""
import json

import pytest

from tests.async_mock import patch
from tests.common import load_fixture


@pytest.fixture(name="skip_notifications", autouse=True)
def skip_notifications_fixture():
    """Skip notification calls."""
    with patch("homeassistant.components.persistent_notification.async_create"), patch(
        "homeassistant.components.persistent_notification.async_dismiss"
    ):
        yield


@pytest.fixture(name="climacell_config_flow_connect", autouse=True)
def climacell_config_flow_connect():
    """Mock valid climacell config flow setup."""
    with patch(
        "homeassistant.components.climacell.config_flow.ClimaCell.realtime",
        return_value=load_fixture("climacell/realtime.json"),
    ):
        yield


@pytest.fixture(name="climacell_config_entry_update")
def climacell_config_entry_update_fixture():
    """Mock valid climacell config entry setup."""
    with patch(
        "homeassistant.components.climacell.ClimaCell.realtime",
        return_value=json.loads(load_fixture("climacell/realtime.json")),
    ), patch(
        "homeassistant.components.climacell.ClimaCell.forecast_hourly",
        return_value=json.loads(load_fixture("climacell/hourly.json")),
    ), patch(
        "homeassistant.components.climacell.ClimaCell.forecast_daily",
        return_value=json.loads(load_fixture("climacell/daily.json")),
    ), patch(
        "homeassistant.components.climacell.ClimaCell.forecast_nowcast",
        return_value=json.loads(load_fixture("climacell/nowcast.json")),
    ):
        yield
