"""Provide common pytest fixtures."""
from unittest.mock import patch

import pytest


@pytest.fixture(name="mock_charger")
def test_charger_auth():
    """Mock library calls."""
    with patch("openevsewifi.Charger", autospec=True) as mock_charger:
        mock_charger.status.return_value = "sleeping"
        mock_charger.charge_time_elapsed.return_value = 2.8
        mock_charger.ambient_temperature.return_value = 35.2
        mock_charger.ir_temperature.return_value = 40.1
        mock_charger.rtc_temperature.return_value = 35.6
        mock_charger.usage_session.return_value = 1.5
        mock_charger.usage_total.return_value = 101.4
        yield
