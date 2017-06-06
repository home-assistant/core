"""Test the automatic device tracker platform."""
import asyncio
import logging
from unittest.mock import patch, MagicMock
import aioautomatic

from homeassistant.components.device_tracker.automatic import (
    async_setup_scanner)

_LOGGER = logging.getLogger(__name__)


@patch('aioautomatic.Client.create_session_from_password')
def test_invalid_credentials(mock_create_session, hass):
    """Test with invalid credentials."""
    @asyncio.coroutine
    def get_session(*args, **kwargs):
        """Return the test session."""
        raise aioautomatic.exceptions.ForbiddenError()

    mock_create_session.side_effect = get_session

    config = {
        'platform': 'automatic',
        'username': 'bad_username',
        'password': 'bad_password',
        'client_id': 'client_id',
        'secret': 'client_secret',
        'devices': None,
    }
    result = hass.loop.run_until_complete(
        async_setup_scanner(hass, config, None))
    assert not result


@patch('aioautomatic.Client.create_session_from_password')
def test_valid_credentials(mock_create_session, hass):
    """Test with valid credentials."""
    session = MagicMock()
    vehicle = MagicMock()
    trip = MagicMock()
    mock_see = MagicMock()

    vehicle.id = 'mock_id'
    vehicle.display_name = 'mock_display_name'
    vehicle.fuel_level_percent = 45.6
    vehicle.latest_location = None

    trip.end_location.lat = 45.567
    trip.end_location.lon = 34.345
    trip.end_location.accuracy_m = 5.6

    @asyncio.coroutine
    def get_session(*args, **kwargs):
        """Return the test session."""
        return session

    @asyncio.coroutine
    def get_vehicles(*args, **kwargs):
        """Return list of test vehicles."""
        return [vehicle]

    @asyncio.coroutine
    def get_trips(*args, **kwargs):
        """Return list of test trips."""
        return [trip]

    mock_create_session.side_effect = get_session
    session.get_vehicles.side_effect = get_vehicles
    session.get_trips.side_effect = get_trips

    config = {
        'platform': 'automatic',
        'username': 'bad_username',
        'password': 'bad_password',
        'client_id': 'client_id',
        'secret': 'client_secret',
        'devices': None,
    }
    result = hass.loop.run_until_complete(
        async_setup_scanner(hass, config, mock_see))

    assert result
    assert mock_see.called
    assert len(mock_see.mock_calls) == 2
    assert mock_see.mock_calls[0][2]['dev_id'] == 'mock_id'
    assert mock_see.mock_calls[0][2]['mac'] == 'mock_id'
    assert mock_see.mock_calls[0][2]['host_name'] == 'mock_display_name'
    assert mock_see.mock_calls[0][2]['attributes'] == {'fuel_level': 45.6}
    assert mock_see.mock_calls[0][2]['gps'] == (45.567, 34.345)
    assert mock_see.mock_calls[0][2]['gps_accuracy'] == 5.6
