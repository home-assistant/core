"""Fixtures for the Whirlpool Sixth Sense integration tests."""
from unittest import mock
from unittest.mock import AsyncMock

import pytest
import whirlpool

MOCK_SAID = "said1"


@pytest.fixture(name="mock_auth_api")
def fixture_mock_auth_api():
    """Set up air conditioner Auth fixture."""
    with mock.patch("homeassistant.components.whirlpool.Auth") as mock_auth:
        mock_auth.return_value.do_auth = AsyncMock()
        mock_auth.return_value.is_access_token_valid.return_value = True
        mock_auth.return_value.get_said_list.return_value = [MOCK_SAID]
        yield mock_auth


@pytest.fixture(name="mock_aircon_api", autouse=True)
def fixture_mock_aircon_api(mock_auth_api):
    """Set up air conditioner API fixture."""
    with mock.patch(
        "homeassistant.components.whirlpool.climate.Aircon"
    ) as mock_aircon_api:
        mock_aircon_api.return_value.connect = AsyncMock()
        mock_aircon_api.return_value.fetch_name = AsyncMock(return_value="TestZone")
        mock_aircon_api.return_value.said = MOCK_SAID
        mock_aircon_api.return_value.get_online.return_value = True
        mock_aircon_api.return_value.get_power_on.return_value = True
        mock_aircon_api.return_value.get_mode.return_value = whirlpool.aircon.Mode.Cool
        mock_aircon_api.return_value.get_fanspeed.return_value = (
            whirlpool.aircon.FanSpeed.Auto
        )
        mock_aircon_api.return_value.get_current_temp.return_value = 15
        mock_aircon_api.return_value.get_temp.return_value = 20
        mock_aircon_api.return_value.get_current_humidity.return_value = 80
        mock_aircon_api.return_value.get_humidity.return_value = 50
        mock_aircon_api.return_value.get_h_louver_swing.return_value = True
        yield mock_aircon_api
