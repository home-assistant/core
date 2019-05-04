"""Tests for the Withings component."""
import datetime

from asynctest import patch, MagicMock
import callee
import nokia
from oauthlib.oauth2.rfc6749.errors import MissingTokenError
import pytest
from requests_oauthlib import TokenUpdated

from homeassistant.components.withings.common import (
    NotAuthenticatedError,
    ServiceError,
    WithingsDataManager,
)
from homeassistant.exceptions import PlatformNotReady


@pytest.fixture(name='nokia_api')
def nokia_api_fixture():
    """Provide nokia api."""
    nokia_api = nokia.NokiaApi.__new__(nokia.NokiaApi)
    nokia_api.get_measures = MagicMock()
    nokia_api.get_sleep = MagicMock()
    return nokia_api


@pytest.fixture(name='data_manager')
def data_manager_fixture(nokia_api: nokia.NokiaApi):
    """Provide data manager."""
    return WithingsDataManager(
        'My Profile',
        nokia_api
    )


def test_data_manager_init(
        data_manager: WithingsDataManager,
        nokia_api: nokia.NokiaApi
):
    """Test method."""
    assert data_manager.profile == 'My Profile'
    assert data_manager.api == nokia_api
    assert data_manager.slug == 'my_profile'


def test_data_manager_check_authenticated(
        data_manager: WithingsDataManager,
        nokia_api: nokia.NokiaApi
):
    """Test method."""
    nokia_api.request = MagicMock(return_value='DATA')
    results1 = data_manager.check_authenticated()
    nokia_api.request.assert_called_with('user', 'getdevice', version='v2')
    assert results1 == 'DATA'

    nokia_api.request.reset_mock()

    nokia_api.request = MagicMock(return_value='DATA_NEW')
    data_manager.check_authenticated()
    nokia_api.request.assert_not_called()


def test_data_manager_update_measures(
        data_manager: WithingsDataManager,
        nokia_api: nokia.NokiaApi
):
    """Test method."""
    nokia_api.get_measures = MagicMock(return_value='DATA')
    results1 = data_manager.update_measures()
    nokia_api.get_measures.assert_called_with()
    assert results1 == 'DATA'

    nokia_api.get_measures.reset_mock()

    nokia_api.get_measures = MagicMock(return_value='DATA_NEW')
    data_manager.update_measures()
    nokia_api.get_measures.assert_not_called()


def test_data_manager_update_sleep(
        data_manager: WithingsDataManager,
        nokia_api: nokia.NokiaApi
):
    """Test method."""
    with patch('time.time', return_value=100000.101):
        nokia_api.get_sleep = MagicMock(return_value='DATA')
        results1 = data_manager.update_sleep()
        nokia_api.get_sleep.assert_called_with(
            startdate=78400,
            enddate=100000
        )
        assert results1 == 'DATA'

        nokia_api.get_sleep.reset_mock()

        nokia_api.get_sleep = MagicMock(return_value='DATA_NEW')
        data_manager.update_sleep()
        nokia_api.get_sleep.assert_not_called()


def test_data_manager_update_sleep_summary(
        data_manager: WithingsDataManager,
        nokia_api: nokia.NokiaApi
):
    """Test method."""
    now = datetime.datetime.utcnow()
    noon = datetime.datetime(
        now.year, now.month, now.day,
        12, 0, 0, 0,
        datetime.timezone.utc
    )
    yesterday_noon_timestamp = noon.timestamp() - 86400

    nokia_api.get_sleep_summary = MagicMock(return_value='DATA')
    results1 = data_manager.update_sleep_summary()
    nokia_api.get_sleep_summary.assert_called_with(
        lastupdate=callee.And(
            callee.GreaterOrEqualTo(yesterday_noon_timestamp),
            callee.LessThan(yesterday_noon_timestamp + 10)
        )
    )
    assert results1 == 'DATA'

    nokia_api.get_sleep_summary.reset_mock()

    nokia_api.get_sleep_summary = MagicMock(return_value='DATA_NEW')
    data_manager.update_sleep_summary()
    nokia_api.get_sleep_summary.assert_not_called()


def test_print_service():
    """Test method."""
    # Go from None to True
    WithingsDataManager.service_available = None
    assert WithingsDataManager.print_service_available()
    assert WithingsDataManager.service_available is True
    assert not WithingsDataManager.print_service_available()
    assert not WithingsDataManager.print_service_available()

    # Go from True to False
    assert WithingsDataManager.print_service_unavailable()
    assert WithingsDataManager.service_available is False
    assert not WithingsDataManager.print_service_unavailable()
    assert not WithingsDataManager.print_service_unavailable()

    # Go from False to True
    assert WithingsDataManager.print_service_available()
    assert WithingsDataManager.service_available is True
    assert not WithingsDataManager.print_service_available()
    assert not WithingsDataManager.print_service_available()

    # Go from Non to False
    WithingsDataManager.service_available = None
    assert WithingsDataManager.print_service_unavailable()
    assert WithingsDataManager.service_available is False
    assert not WithingsDataManager.print_service_unavailable()
    assert not WithingsDataManager.print_service_unavailable()


def test_data_manager_call():
    """Test method."""
    # Token refreshed.
    def hello_func():
        return 'HELLO2'

    function = MagicMock(side_effect=[
        TokenUpdated('my_token'),
        hello_func(),
    ])
    result = WithingsDataManager.call(function)
    assert result == 'HELLO2'
    assert function.call_count == 2

    # Too many token refreshes.
    function = MagicMock(side_effect=[
        TokenUpdated('my_token'),
        TokenUpdated('my_token'),
    ])
    try:
        result = WithingsDataManager.call(function)
        assert False, "This should not have ran."
    except ServiceError:
        assert True
    assert function.call_count == 2

    # Not authenticated 1.
    test_function = MagicMock(side_effect=MissingTokenError('Error Code 401'))
    try:
        result = WithingsDataManager.call(test_function)
        assert False, "An exception should have been thrown."
    except NotAuthenticatedError:
        assert True

    # Not authenticated 2.
    test_function = MagicMock(side_effect=Exception('Error Code 401'))
    try:
        result = WithingsDataManager.call(test_function)
        assert False, "An exception should have been thrown."
    except NotAuthenticatedError:
        assert True

    # Service error.
    test_function = MagicMock(side_effect=PlatformNotReady())
    try:
        result = WithingsDataManager.call(test_function)
        assert False, "An exception should have been thrown."
    except PlatformNotReady:
        assert True
