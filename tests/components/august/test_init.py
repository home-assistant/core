"""The tests for the august platform."""
import asyncio
from unittest.mock import MagicMock

from august.lock import LockDetail
from requests import RequestException

from homeassistant.components import august
from homeassistant.exceptions import HomeAssistantError

from tests.components.august.mocks import (
    MockAugustApiFailing,
    MockAugustComponentData,
    _mock_august_authentication,
    _mock_august_authenticator,
    _mock_august_lock,
    _mock_doorsense_enabled_august_lock_detail,
    _mock_doorsense_missing_august_lock_detail,
    _mock_inoperative_august_lock_detail,
    _mock_operative_august_lock_detail,
)


def test_get_lock_name():
    """Get the lock name from August data."""
    data = MockAugustComponentData(last_lock_status_update_timestamp=1)
    lock = _mock_august_lock()
    data.set_mocked_locks([lock])
    assert data.get_lock_name("mocklockid1") == "mocklockid1 Name"


def test_unlock_throws_august_api_http_error():
    """Test unlock."""
    data = MockAugustComponentData(api=MockAugustApiFailing())
    lock = _mock_august_lock()
    data.set_mocked_locks([lock])
    last_err = None
    try:
        data.unlock("mocklockid1")
    except HomeAssistantError as err:
        last_err = err
    assert (
        str(last_err)
        == "mocklockid1 Name: This should bubble up as its user consumable"
    )


def test_lock_throws_august_api_http_error():
    """Test lock."""
    data = MockAugustComponentData(api=MockAugustApiFailing())
    lock = _mock_august_lock()
    data.set_mocked_locks([lock])
    last_err = None
    try:
        data.unlock("mocklockid1")
    except HomeAssistantError as err:
        last_err = err
    assert (
        str(last_err)
        == "mocklockid1 Name: This should bubble up as its user consumable"
    )


def test_inoperative_locks_are_filtered_out():
    """Ensure inoperative locks do not get setup."""
    august_operative_lock = _mock_operative_august_lock_detail("oplockid1")
    data = _create_august_data_with_lock_details(
        [august_operative_lock, _mock_inoperative_august_lock_detail("inoplockid1")]
    )

    assert len(data.locks) == 1
    assert data.locks[0].device_id == "oplockid1"


def test_lock_has_doorsense():
    """Check to see if a lock has doorsense."""
    data = _create_august_data_with_lock_details(
        [
            _mock_doorsense_enabled_august_lock_detail("doorsenselock1"),
            _mock_doorsense_missing_august_lock_detail("nodoorsenselock1"),
            RequestException("mocked request error"),
            RequestException("mocked request error"),
        ]
    )

    assert data.lock_has_doorsense("doorsenselock1") is True
    assert data.lock_has_doorsense("nodoorsenselock1") is False

    # The api calls are mocked to fail on the second
    # run of async_get_lock_detail
    #
    # This will be switched to await data.async_get_lock_detail("doorsenselock1")
    # once we mock the full home assistant setup
    data._update_locks_detail()
    # doorsenselock1 should be false if we cannot tell due
    # to an api error
    assert data.lock_has_doorsense("doorsenselock1") is False


async def test__refresh_access_token(hass):
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


def _create_august_data_with_lock_details(lock_details):
    locks = []
    for lock in lock_details:
        if isinstance(lock, LockDetail):
            locks.append(_mock_august_lock(lock.device_id))
    authentication = _mock_august_authentication("original_token", 1234)
    authenticator = _mock_august_authenticator()
    token_refresh_lock = MagicMock()
    api = MagicMock()
    api.get_lock_status = MagicMock(return_value=(MagicMock(), MagicMock()))
    api.get_lock_detail = MagicMock(side_effect=lock_details)
    api.get_operable_locks = MagicMock(return_value=locks)
    api.get_doorbells = MagicMock(return_value=[])
    return august.AugustData(
        MagicMock(), api, authentication, authenticator, token_refresh_lock
    )
