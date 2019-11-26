"""Tests for the Withings component."""
from asynctest import MagicMock

import pytest
from withings_api import WithingsApi
from withings_api.common import UnauthorizedException, TimeoutException

from homeassistant.exceptions import PlatformNotReady
from homeassistant.components.withings.common import (
    NotAuthenticatedError,
    WithingsDataManager,
)


@pytest.fixture(name="withings_api")
def withings_api_fixture() -> WithingsApi:
    """Provide withings api."""
    withings_api = WithingsApi.__new__(WithingsApi)
    withings_api.get_measures = MagicMock()
    withings_api.get_sleep = MagicMock()
    return withings_api


@pytest.fixture(name="data_manager")
def data_manager_fixture(hass, withings_api: WithingsApi) -> WithingsDataManager:
    """Provide data manager."""
    return WithingsDataManager(hass, "My Profile", withings_api)


def test_print_service() -> None:
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


async def test_data_manager_call(data_manager: WithingsDataManager) -> None:
    """Test method."""
    # Not authenticated 1.
    test_function = MagicMock(side_effect=UnauthorizedException(401))
    with pytest.raises(NotAuthenticatedError):
        await data_manager.call(test_function)

    # Not authenticated 2.
    test_function = MagicMock(side_effect=TimeoutException(522))
    with pytest.raises(PlatformNotReady):
        await data_manager.call(test_function)

    # Service error.
    test_function = MagicMock(side_effect=PlatformNotReady())
    with pytest.raises(PlatformNotReady):
        await data_manager.call(test_function)


async def test_data_manager_call_throttle_enabled(
    data_manager: WithingsDataManager,
) -> None:
    """Test method."""
    hello_func = MagicMock(return_value="HELLO2")

    result = await data_manager.call(hello_func, throttle_domain="test")
    assert result == "HELLO2"

    result = await data_manager.call(hello_func, throttle_domain="test")
    assert result == "HELLO2"

    assert hello_func.call_count == 1


async def test_data_manager_call_throttle_disabled(
    data_manager: WithingsDataManager,
) -> None:
    """Test method."""
    hello_func = MagicMock(return_value="HELLO2")

    result = await data_manager.call(hello_func)
    assert result == "HELLO2"

    result = await data_manager.call(hello_func)
    assert result == "HELLO2"

    assert hello_func.call_count == 2
