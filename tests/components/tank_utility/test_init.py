"""Tests for the Tank Utility integration setup and teardown."""

from unittest.mock import MagicMock, patch

import pytest
import requests

from homeassistant.components.tank_utility.const import DOMAIN
from homeassistant.components.tank_utility.coordinator import (
    TankUtilityDataUpdateCoordinator,
)
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.update_coordinator import UpdateFailed

from .conftest import DEVICE_DATA, MOCK_DEVICE_ID, TEST_EMAIL, TEST_PASSWORD

from tests.common import MockConfigEntry


def _mock_http_error(status_code: int) -> requests.exceptions.HTTPError:
    """Create a mock HTTPError with a response."""
    response = requests.Response()
    response.status_code = status_code
    return requests.exceptions.HTTPError(response=response)


@pytest.mark.usefixtures("mock_get_data")
async def test_setup_and_unload_entry(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test successful setup and unload of a config entry."""
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.LOADED
    assert isinstance(mock_config_entry.runtime_data, TankUtilityDataUpdateCoordinator)

    assert await hass.config_entries.async_unload(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.NOT_LOADED


async def test_setup_entry_auth_failed(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_get_data: MagicMock,
) -> None:
    """Test setup entry when authentication fails triggers reauth."""
    mock_get_data.side_effect = _mock_http_error(requests.codes.unauthorized)

    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.SETUP_ERROR

    flows = hass.config_entries.flow.async_progress()
    assert len(flows) == 1
    assert flows[0]["step_id"] == "reauth_confirm"
    assert flows[0]["handler"] == DOMAIN


@pytest.mark.parametrize(
    "exception",
    [
        requests.exceptions.ConnectTimeout,
        _mock_http_error(requests.codes.internal_server_error),
    ],
)
async def test_setup_entry_cannot_connect(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_get_data: MagicMock,
    exception: Exception,
) -> None:
    """Test setup entry when network connection fails initiates setup retry."""
    mock_get_data.side_effect = exception

    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.SETUP_RETRY


async def test_coordinator_error_sanitization_and_suppressed_chain(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_get_data: MagicMock,
) -> None:
    """Test coordinator errors do not leak tokens from URLs and suppress cause chain."""
    token = "secret_token_12345"
    token_url = f"https://data.tankutility.com/api/devices?token={token}"

    response = requests.Response()
    response.status_code = requests.codes.internal_server_error
    response.url = token_url
    request = requests.PreparedRequest()
    request.url = token_url
    response.request = request
    http_error = requests.exceptions.HTTPError(
        f"500 Server Error for url: {token_url}",
        response=response,
        request=request,
    )
    mock_get_data.side_effect = http_error

    coordinator = TankUtilityDataUpdateCoordinator(hass, mock_config_entry)
    with pytest.raises(UpdateFailed) as exc_info:
        await coordinator._async_update_data()

    assert token not in str(exc_info.value)
    assert exc_info.value.__cause__ is None
    assert exc_info.value.__suppress_context__ is True
    assert str(exc_info.value) == "Error communicating with Tank Utility: HTTP 500"

    # Test 401 Unauthorized suppresses chain and does not leak token
    auth_response = requests.Response()
    auth_response.status_code = requests.codes.unauthorized
    auth_response.url = token_url
    auth_response.request = request
    auth_error = requests.exceptions.HTTPError(
        f"401 Client Error for url: {token_url}",
        response=auth_response,
        request=request,
    )
    mock_get_data.side_effect = auth_error

    with pytest.raises(ConfigEntryAuthFailed) as exc_info:
        await coordinator._async_update_data()

    assert token not in str(exc_info.value)
    assert exc_info.value.__cause__ is None
    assert exc_info.value.__suppress_context__ is True
    assert str(exc_info.value) == "Invalid credentials"

    # Test RequestException suppresses chain and does not leak token
    connect_error = requests.exceptions.ConnectTimeout(
        f"Connection to {token_url} timed out"
    )
    mock_get_data.side_effect = connect_error

    with pytest.raises(UpdateFailed) as exc_info:
        await coordinator._async_update_data()

    assert token not in str(exc_info.value)
    assert exc_info.value.__cause__ is None
    assert exc_info.value.__suppress_context__ is True
    assert (
        str(exc_info.value) == "Error communicating with Tank Utility: ConnectTimeout"
    )

    # Test HTTPError without response
    http_error_no_resp = requests.exceptions.HTTPError(
        f"HTTP Error for url: {token_url}"
    )
    mock_get_data.side_effect = http_error_no_resp

    with pytest.raises(UpdateFailed) as exc_info:
        await coordinator._async_update_data()

    assert token not in str(exc_info.value)
    assert exc_info.value.__cause__ is None
    assert exc_info.value.__suppress_context__ is True
    assert str(exc_info.value) == "Error communicating with Tank Utility: HTTPError"


async def test_coordinator_device_detail_token_refresh(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test device-detail 401 refreshes expired token and retries with finite timeouts."""
    with (
        patch(
            "tank_utility.device.auth.get_token",
            side_effect=["expired_token", "fresh_token"],
        ) as mock_token,
        patch(
            "tank_utility.device.get_devices",
            return_value=[MOCK_DEVICE_ID],
        ) as mock_devices,
        patch(
            "tank_utility.device.get_device_data",
            side_effect=[
                _mock_http_error(requests.codes.unauthorized),
                dict(DEVICE_DATA),
            ],
        ) as mock_device_data,
    ):
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.LOADED
    assert mock_token.call_count == 2
    mock_token.assert_any_call(TEST_EMAIL, TEST_PASSWORD, timeout=(10, 30))
    mock_token.assert_any_call(TEST_EMAIL, TEST_PASSWORD, force=True, timeout=(10, 30))
    mock_devices.assert_called_once_with("expired_token", timeout=(10, 30))
    assert mock_device_data.call_count == 2
    mock_device_data.assert_any_call("expired_token", MOCK_DEVICE_ID, timeout=(10, 30))
    mock_device_data.assert_any_call("fresh_token", MOCK_DEVICE_ID, timeout=(10, 30))


async def test_coordinator_device_detail_bad_request_token_refresh(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test device-detail 400 refreshes cached token and retries."""
    with (
        patch(
            "tank_utility.device.auth.get_token",
            side_effect=["expired_token", "fresh_token", "fresh_token"],
        ) as mock_token,
        patch(
            "tank_utility.device.get_devices",
            return_value=[MOCK_DEVICE_ID],
        ) as mock_devices,
        patch(
            "tank_utility.device.get_device_data",
            side_effect=[
                _mock_http_error(requests.codes.bad_request),
                dict(DEVICE_DATA),
            ],
        ) as mock_device_data,
    ):
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.LOADED
    assert mock_token.call_count == 3
    mock_token.assert_any_call(TEST_EMAIL, TEST_PASSWORD, force=True)
    assert mock_devices.call_count == 2
    assert mock_device_data.call_count == 2
    mock_device_data.assert_any_call("expired_token", MOCK_DEVICE_ID, timeout=(10, 30))
    mock_device_data.assert_any_call("fresh_token", MOCK_DEVICE_ID, timeout=(10, 30))
