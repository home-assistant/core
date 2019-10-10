"""Tests for the Withings component."""
from asynctest import MagicMock
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


@pytest.fixture(name="nokia_api")
def nokia_api_fixture():
    """Provide nokia api."""
    nokia_api = nokia.NokiaApi.__new__(nokia.NokiaApi)
    nokia_api.get_measures = MagicMock()
    nokia_api.get_sleep = MagicMock()
    return nokia_api


@pytest.fixture(name="data_manager")
def data_manager_fixture(hass, nokia_api: nokia.NokiaApi):
    """Provide data manager."""
    return WithingsDataManager(hass, "My Profile", nokia_api)


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


async def test_data_manager_call(data_manager):
    """Test method."""
    # Token refreshed.
    def hello_func():
        return "HELLO2"

    function = MagicMock(side_effect=[TokenUpdated("my_token"), hello_func()])
    result = await data_manager.call(function)
    assert result == "HELLO2"
    assert function.call_count == 2

    # Too many token refreshes.
    function = MagicMock(
        side_effect=[TokenUpdated("my_token"), TokenUpdated("my_token")]
    )
    try:
        result = await data_manager.call(function)
        assert False, "This should not have ran."
    except ServiceError:
        assert True
    assert function.call_count == 2

    # Not authenticated 1.
    test_function = MagicMock(side_effect=MissingTokenError("Error Code 401"))
    try:
        result = await data_manager.call(test_function)
        assert False, "An exception should have been thrown."
    except NotAuthenticatedError:
        assert True

    # Not authenticated 2.
    test_function = MagicMock(side_effect=Exception("Error Code 401"))
    try:
        result = await data_manager.call(test_function)
        assert False, "An exception should have been thrown."
    except NotAuthenticatedError:
        assert True

    # Service error.
    test_function = MagicMock(side_effect=PlatformNotReady())
    try:
        result = await data_manager.call(test_function)
        assert False, "An exception should have been thrown."
    except PlatformNotReady:
        assert True


async def test_data_manager_call_throttle_enabled(data_manager):
    """Test method."""
    hello_func = MagicMock(return_value="HELLO2")

    result = await data_manager.call(hello_func, throttle_domain="test")
    assert result == "HELLO2"

    result = await data_manager.call(hello_func, throttle_domain="test")
    assert result == "HELLO2"

    assert hello_func.call_count == 1


async def test_data_manager_call_throttle_disabled(data_manager):
    """Test method."""
    hello_func = MagicMock(return_value="HELLO2")

    result = await data_manager.call(hello_func)
    assert result == "HELLO2"

    result = await data_manager.call(hello_func)
    assert result == "HELLO2"

    assert hello_func.call_count == 2
