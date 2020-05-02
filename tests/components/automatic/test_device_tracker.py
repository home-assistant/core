"""Test the automatic device tracker platform."""
from datetime import datetime
import logging

import aioautomatic

from homeassistant.components.automatic.device_tracker import async_setup_scanner
from homeassistant.setup import async_setup_component

from tests.async_mock import MagicMock, patch

_LOGGER = logging.getLogger(__name__)


@patch("aioautomatic.Client.create_session_from_refresh_token")
@patch("json.load")
@patch("json.dump")
@patch("os.makedirs")
@patch("os.path.isfile", return_value=True)
@patch("homeassistant.components.automatic.device_tracker.open", create=True)
def test_invalid_credentials(
    mock_open,
    mock_isfile,
    mock_makedirs,
    mock_json_dump,
    mock_json_load,
    mock_create_session,
    hass,
):
    """Test with invalid credentials."""
    hass.loop.run_until_complete(async_setup_component(hass, "http", {}))
    mock_json_load.return_value = {"refresh_token": "bad_token"}

    async def get_session(*args, **kwargs):
        """Return the test session."""
        raise aioautomatic.exceptions.BadRequestError("err_invalid_refresh_token")

    mock_create_session.side_effect = get_session

    config = {
        "platform": "automatic",
        "client_id": "client_id",
        "secret": "client_secret",
        "devices": None,
    }
    hass.loop.run_until_complete(async_setup_scanner(hass, config, None))
    assert mock_create_session.called
    assert len(mock_create_session.mock_calls) == 1
    assert mock_create_session.mock_calls[0][1][0] == "bad_token"


@patch("aioautomatic.Client.create_session_from_refresh_token")
@patch("aioautomatic.Client.ws_connect")
@patch("json.load")
@patch("json.dump")
@patch("os.makedirs")
@patch("os.path.isfile", return_value=True)
@patch("homeassistant.components.automatic.device_tracker.open", create=True)
def test_valid_credentials(
    mock_open,
    mock_isfile,
    mock_makedirs,
    mock_json_dump,
    mock_json_load,
    mock_ws_connect,
    mock_create_session,
    hass,
):
    """Test with valid credentials."""
    hass.loop.run_until_complete(async_setup_component(hass, "http", {}))
    mock_json_load.return_value = {"refresh_token": "good_token"}

    session = MagicMock()
    vehicle = MagicMock()
    trip = MagicMock()
    mock_see = MagicMock()

    vehicle.id = "mock_id"
    vehicle.display_name = "mock_display_name"
    vehicle.fuel_level_percent = 45.6
    vehicle.latest_location = None
    vehicle.updated_at = datetime(2017, 8, 13, 1, 2, 3)

    trip.end_location.lat = 45.567
    trip.end_location.lon = 34.345
    trip.end_location.accuracy_m = 5.6
    trip.ended_at = datetime(2017, 8, 13, 1, 2, 4)

    async def get_session(*args, **kwargs):
        """Return the test session."""
        return session

    async def get_vehicles(*args, **kwargs):
        """Return list of test vehicles."""
        return [vehicle]

    async def get_trips(*args, **kwargs):
        """Return list of test trips."""
        return [trip]

    mock_create_session.side_effect = get_session
    session.ws_connect = MagicMock()
    session.get_vehicles.side_effect = get_vehicles
    session.get_trips.side_effect = get_trips
    session.refresh_token = "mock_refresh_token"

    config = {
        "platform": "automatic",
        "username": "good_username",
        "password": "good_password",
        "client_id": "client_id",
        "secret": "client_secret",
        "devices": None,
    }
    result = hass.loop.run_until_complete(async_setup_scanner(hass, config, mock_see))

    assert result

    assert mock_ws_connect.called
    assert len(mock_ws_connect.mock_calls) == 2

    assert mock_create_session.called
    assert len(mock_create_session.mock_calls) == 1
    assert mock_create_session.mock_calls[0][1][0] == "good_token"

    assert mock_see.called
    assert len(mock_see.mock_calls) == 2
    assert mock_see.mock_calls[0][2]["dev_id"] == "mock_id"
    assert mock_see.mock_calls[0][2]["mac"] == "mock_id"
    assert mock_see.mock_calls[0][2]["host_name"] == "mock_display_name"
    assert mock_see.mock_calls[0][2]["attributes"] == {"fuel_level": 45.6}
    assert mock_see.mock_calls[0][2]["gps"] == (45.567, 34.345)
    assert mock_see.mock_calls[0][2]["gps_accuracy"] == 5.6

    assert mock_json_dump.called
    assert len(mock_json_dump.mock_calls) == 1
    assert mock_json_dump.mock_calls[0][1][0] == {"refresh_token": "mock_refresh_token"}
