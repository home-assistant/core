"""The tests for the august platform."""
import asyncio
from unittest.mock import MagicMock

from homeassistant.components import august
from homeassistant.exceptions import HomeAssistantError

from tests.components.august.mocks import (
    MockAugustApiFailing,
    MockAugustData,
    _mock_august_authentication,
    _mock_august_authenticator,
)


def test_get_lock_name():
    """Get the lock name from August data."""
    data = MockAugustData(last_lock_status_update_timestamp=1)
    assert data.get_lock_name("mockdeviceid1") == "Mocked Lock 1"


def test_unlock_throws_august_api_http_error():
    """Test unlock."""
    data = MockAugustData(api=MockAugustApiFailing())
    last_err = None
    try:
        data.unlock("mockdeviceid1")
    except HomeAssistantError as err:
        last_err = err
    assert (
        str(last_err) == "Mocked Lock 1: This should bubble up as its user consumable"
    )


def test_lock_throws_august_api_http_error():
    """Test lock."""
    data = MockAugustData(api=MockAugustApiFailing())
    last_err = None
    try:
        data.unlock("mockdeviceid1")
    except HomeAssistantError as err:
        last_err = err
    assert (
        str(last_err) == "Mocked Lock 1: This should bubble up as its user consumable"
    )


def test__refresh_access_token():
    """Test refresh of the access token."""
    authentication = _mock_august_authentication("original_token", 1234)
    authenticator = _mock_august_authenticator()
    token_refresh_lock = asyncio.Lock()

    data = august.AugustData(
        hass, MagicMock(name="api"), authentication, authenticator, token_refresh_lock
    )
    await data._async_refresh_access_token_if_needed()
    authenticator.refresh_access_token.assert_not_called()

    authenticator.should_refresh.return_value = 1
    authenticator.refresh_access_token.return_value = _mock_august_authentication(
        "new_token", 5678
    )
    await data._async_refresh_access_token_if_needed()
    authenticator.refresh_access_token.assert_called()
    assert data._access_token == "new_token"
    assert data._access_token_expires == 5678
