"""Fixtures for the Whirlpool Sixth Sense integration tests."""
from unittest import mock
from unittest.mock import AsyncMock

import pytest
import whirlpool
import whirlpool.aircon

MOCK_SAID1 = "said1"
MOCK_SAID2 = "said2"


@pytest.fixture(name="mock_auth_api")
def fixture_mock_auth_api():
    """Set up air conditioner Auth fixture."""
    with mock.patch("homeassistant.components.whirlpool.Auth") as mock_auth:
        mock_auth.return_value.do_auth = AsyncMock()
        mock_auth.return_value.is_access_token_valid.return_value = True
        mock_auth.return_value.get_said_list.return_value = [MOCK_SAID1, MOCK_SAID2]
        yield mock_auth


def get_aircon_mock(said):
    """Get a mock of an air conditioner."""
    mock_aircon = mock.Mock(said=said)
    mock_aircon.connect = AsyncMock()
    mock_aircon.fetch_name = AsyncMock(return_value="TestZone")
    mock_aircon.get_online.return_value = True
    mock_aircon.get_power_on.return_value = True
    mock_aircon.get_mode.return_value = whirlpool.aircon.Mode.Cool
    mock_aircon.get_fanspeed.return_value = whirlpool.aircon.FanSpeed.Auto
    mock_aircon.get_current_temp.return_value = 15
    mock_aircon.get_temp.return_value = 20
    mock_aircon.get_current_humidity.return_value = 80
    mock_aircon.get_humidity.return_value = 50
    mock_aircon.get_h_louver_swing.return_value = True

    mock_aircon.set_power_on = AsyncMock()
    mock_aircon.set_mode = AsyncMock()
    mock_aircon.set_temp = AsyncMock()
    mock_aircon.set_humidity = AsyncMock()
    mock_aircon.set_mode = AsyncMock()
    mock_aircon.set_fanspeed = AsyncMock()
    mock_aircon.set_h_louver_swing = AsyncMock()

    return mock_aircon


@pytest.fixture(name="mock_aircon1_api", autouse=True)
def fixture_mock_aircon1_api(mock_auth_api):
    """Set up air conditioner API fixture."""
    yield get_aircon_mock(MOCK_SAID1)


@pytest.fixture(name="mock_aircon2_api", autouse=True)
def fixture_mock_aircon2_api(mock_auth_api):
    """Set up air conditioner API fixture."""
    yield get_aircon_mock(MOCK_SAID2)


@pytest.fixture(name="mock_aircon_api_instances", autouse=True)
def fixture_mock_aircon_api_instances(mock_aircon1_api, mock_aircon2_api):
    """Set up air conditioner API fixture."""
    with mock.patch(
        "homeassistant.components.whirlpool.climate.Aircon"
    ) as mock_aircon_api:
        mock_aircon_api.side_effect = [mock_aircon1_api, mock_aircon2_api]
        yield mock_aircon_api
