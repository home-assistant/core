"""Configure py.test."""
import pytest

from tests.async_mock import patch


@pytest.fixture(name="climacell_connect", autouse=True)
def climacell_connect_fixture():
    """Mock valid climacell config flow and entry setup."""
    with patch(
        "homeassistant.components.climacell.config_flow.ClimaCell.realtime",
        return_value={},
    ), patch(
        "homeassistant.components.climacell.ClimaCell.realtime", return_value={},
    ), patch(
        "homeassistant.components.climacell.ClimaCell.forecast_hourly", return_value=[],
    ), patch(
        "homeassistant.components.climacell.ClimaCell.forecast_daily", return_value=[],
    ):
        yield
