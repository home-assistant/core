"""Tests for Verisure integration setup and session handling."""

from unittest.mock import MagicMock, patch

import pytest
from verisure import (
    AuthenticationError,
    CookieReadError,
    Error as VerisureBaseError,
    LoginError,
    RateLimitError,
    RequestError,
    ResponseError,
)

from homeassistant.components.verisure.const import DOMAIN
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry


async def _async_setup(hass: HomeAssistant, mock_config_entry: MockConfigEntry) -> None:
    """Set up the Verisure integration."""
    mock_config_entry.add_to_hass(hass)
    with patch("homeassistant.components.verisure.PLATFORMS", []):
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()


async def _async_trigger_coordinator_update(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Trigger a coordinator refresh after setup."""
    await mock_config_entry.runtime_data.async_refresh()
    await hass.async_block_till_done()


async def test_setup_success(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_verisure: MagicMock,
) -> None:
    """Test successful setup loads the config entry."""
    await _async_setup(hass, mock_config_entry)

    assert mock_config_entry.state is ConfigEntryState.LOADED
    mock_verisure.login_cookie.assert_called_once()
    mock_verisure.set_giid.assert_called_once()


@pytest.mark.parametrize(
    "exc",
    [
        RequestError("network"),
        ResponseError(503, "server error"),
        RateLimitError("rate limited"),
    ],
)
async def test_setup_transient_login_failure(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_verisure: MagicMock,
    exc: Exception,
) -> None:
    """Transient failures during login put the entry in SETUP_RETRY."""
    mock_verisure.login_cookie.side_effect = exc

    await _async_setup(hass, mock_config_entry)

    assert mock_config_entry.state is ConfigEntryState.SETUP_RETRY
    mock_verisure.set_giid.assert_not_called()


async def test_setup_authentication_error(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_verisure: MagicMock,
) -> None:
    """Invalid credentials during login put the entry in SETUP_ERROR."""
    mock_verisure.login_cookie.side_effect = AuthenticationError(
        "auth failed", status_code=401
    )

    await _async_setup(hass, mock_config_entry)

    assert mock_config_entry.state is ConfigEntryState.SETUP_ERROR
    flows = hass.config_entries.flow.async_progress_by_handler(DOMAIN)
    assert len(flows) == 1
    assert flows[0]["context"]["source"] == "reauth"


async def test_setup_cookie_read_uses_password_login(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_verisure: MagicMock,
) -> None:
    """Unreadable cookie file falls back to password login during setup."""
    mock_verisure.login_cookie.side_effect = CookieReadError("Failed to read cookie")

    await _async_setup(hass, mock_config_entry)

    assert mock_config_entry.state is ConfigEntryState.LOADED
    mock_verisure.login.assert_called_once()
    mock_verisure.set_giid.assert_called_once()


async def test_setup_cookie_read_transient_password_login(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_verisure: MagicMock,
) -> None:
    """Transient password login after cookie read puts the entry in SETUP_RETRY."""
    mock_verisure.login_cookie.side_effect = CookieReadError("Failed to read cookie")
    mock_verisure.login.side_effect = RequestError("offline")

    await _async_setup(hass, mock_config_entry)

    assert mock_config_entry.state is ConfigEntryState.SETUP_RETRY
    mock_verisure.set_giid.assert_not_called()


async def test_setup_cookie_read_authentication_error(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_verisure: MagicMock,
) -> None:
    """Authentication failure after cookie read puts the entry in SETUP_ERROR."""
    mock_verisure.login_cookie.side_effect = CookieReadError("Failed to read cookie")
    mock_verisure.login.side_effect = AuthenticationError(
        "bad credentials", status_code=401
    )

    await _async_setup(hass, mock_config_entry)

    assert mock_config_entry.state is ConfigEntryState.SETUP_ERROR


async def test_setup_unexpected_verisure_error(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_verisure: MagicMock,
) -> None:
    """Unexpected Verisure errors during login put the entry in SETUP_RETRY."""
    mock_verisure.login_cookie.side_effect = VerisureBaseError("unknown")

    await _async_setup(hass, mock_config_entry)

    assert mock_config_entry.state is ConfigEntryState.SETUP_RETRY


async def test_setup_login_error(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_verisure: MagicMock,
) -> None:
    """LoginError during setup puts the entry in SETUP_ERROR."""
    mock_verisure.login_cookie.side_effect = LoginError("login failed")

    await _async_setup(hass, mock_config_entry)

    assert mock_config_entry.state is ConfigEntryState.SETUP_ERROR


@pytest.mark.parametrize(
    "exc",
    [
        RequestError("offline"),
        ResponseError(503, "server error"),
        RateLimitError("rate limited"),
    ],
)
async def test_setup_transient_first_refresh(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_verisure: MagicMock,
    exc: Exception,
) -> None:
    """Transient failures during the first refresh put the entry in SETUP_RETRY."""
    mock_verisure.update_cookie.side_effect = exc

    await _async_setup(hass, mock_config_entry)

    assert mock_config_entry.state is ConfigEntryState.SETUP_RETRY


async def test_setup_authentication_error_recovers_on_first_refresh(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_verisure: MagicMock,
) -> None:
    """Expired session cookie during first refresh is recovered via login_cookie."""
    mock_verisure.update_cookie.side_effect = AuthenticationError(
        "session expired", status_code=401
    )

    await _async_setup(hass, mock_config_entry)

    assert mock_config_entry.state is ConfigEntryState.LOADED
    mock_verisure.login_cookie.assert_called()
    assert mock_config_entry.runtime_data.data["alarm"] == {"status": "DISARMED"}


async def test_setup_cookie_read_on_first_refresh(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_verisure: MagicMock,
) -> None:
    """Corrupt cookie during first refresh re-authenticates with password."""
    mock_verisure.update_cookie.side_effect = CookieReadError("Failed to read cookie")

    await _async_setup(hass, mock_config_entry)

    assert mock_config_entry.state is ConfigEntryState.LOADED
    mock_verisure.login.assert_called_once()


async def test_setup_login_error_recovers_on_first_refresh(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_verisure: MagicMock,
) -> None:
    """Recoverable LoginError during first refresh triggers session recovery."""
    mock_verisure.update_cookie.side_effect = LoginError("token refresh failed")

    await _async_setup(hass, mock_config_entry)

    assert mock_config_entry.state is ConfigEntryState.LOADED
    assert mock_verisure.login_cookie.call_count >= 2


async def test_setup_overview_request_failure(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_verisure: MagicMock,
) -> None:
    """Failures while fetching overview put the entry in SETUP_RETRY."""
    mock_verisure.request.side_effect = RequestError("offline")

    await _async_setup(hass, mock_config_entry)

    assert mock_config_entry.state is ConfigEntryState.SETUP_RETRY


async def test_update_authentication_error_recovers(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_verisure: MagicMock,
) -> None:
    """Expired session during update is recovered without triggering reauth."""
    await _async_setup(hass, mock_config_entry)
    mock_verisure.login_cookie.reset_mock()
    mock_verisure.update_cookie.side_effect = AuthenticationError(
        "session expired", status_code=401
    )

    await _async_trigger_coordinator_update(hass, mock_config_entry)

    assert mock_config_entry.state is ConfigEntryState.LOADED
    mock_verisure.login_cookie.assert_called_once()
    assert not hass.config_entries.flow.async_progress_by_handler(DOMAIN)


async def test_update_authentication_error_triggers_reauth(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_verisure: MagicMock,
) -> None:
    """Authentication failure during session refresh triggers reauth."""
    await _async_setup(hass, mock_config_entry)
    mock_verisure.update_cookie.side_effect = AuthenticationError(
        "session expired", status_code=401
    )
    mock_verisure.login_cookie.side_effect = AuthenticationError(
        "invalid session", status_code=403
    )

    await _async_trigger_coordinator_update(hass, mock_config_entry)

    assert mock_config_entry.state is ConfigEntryState.LOADED
    flows = hass.config_entries.flow.async_progress_by_handler(DOMAIN)
    assert len(flows) == 1
    assert flows[0]["context"]["source"] == "reauth"


async def test_update_cookie_read_password_login(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_verisure: MagicMock,
) -> None:
    """Corrupt cookie during update re-authenticates with password."""
    await _async_setup(hass, mock_config_entry)
    mock_verisure.login.reset_mock()
    mock_verisure.update_cookie.side_effect = CookieReadError("Failed to read cookie")

    await _async_trigger_coordinator_update(hass, mock_config_entry)

    assert mock_config_entry.state is ConfigEntryState.LOADED
    mock_verisure.login.assert_called_once()


async def test_update_cookie_read_password_login_transient(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_verisure: MagicMock,
) -> None:
    """Transient failure during cookie-read password login keeps entry loaded."""
    await _async_setup(hass, mock_config_entry)
    mock_verisure.update_cookie.side_effect = CookieReadError("Failed to read cookie")
    mock_verisure.login.side_effect = RequestError("offline")

    await _async_trigger_coordinator_update(hass, mock_config_entry)

    assert mock_config_entry.state is ConfigEntryState.LOADED
    assert not mock_config_entry.runtime_data.last_update_success


async def test_update_cookie_read_password_login_auth_error(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_verisure: MagicMock,
) -> None:
    """Authentication failure after cookie-read password login triggers reauth."""
    await _async_setup(hass, mock_config_entry)
    mock_verisure.update_cookie.side_effect = CookieReadError("Failed to read cookie")
    mock_verisure.login.side_effect = AuthenticationError(
        "bad credentials", status_code=401
    )

    await _async_trigger_coordinator_update(hass, mock_config_entry)

    assert mock_config_entry.state is ConfigEntryState.LOADED
    flows = hass.config_entries.flow.async_progress_by_handler(DOMAIN)
    assert len(flows) == 1
    assert flows[0]["context"]["source"] == "reauth"


async def test_update_transient_update_cookie(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_verisure: MagicMock,
) -> None:
    """Transient failures during cookie refresh keep the entry loaded."""
    await _async_setup(hass, mock_config_entry)
    mock_verisure.update_cookie.side_effect = RequestError("offline")

    await _async_trigger_coordinator_update(hass, mock_config_entry)

    assert mock_config_entry.state is ConfigEntryState.LOADED
    assert not mock_config_entry.runtime_data.last_update_success


async def test_update_session_refresh_cookie_read_success(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_verisure: MagicMock,
) -> None:
    """Cookie read during session refresh falls back to password login."""
    await _async_setup(hass, mock_config_entry)
    mock_verisure.login.reset_mock()
    mock_verisure.update_cookie.side_effect = AuthenticationError(
        "session expired", status_code=401
    )
    mock_verisure.login_cookie.side_effect = CookieReadError("Failed to read cookie")

    await _async_trigger_coordinator_update(hass, mock_config_entry)

    assert mock_config_entry.state is ConfigEntryState.LOADED
    mock_verisure.login.assert_called_once()


async def test_update_session_refresh_login_error(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_verisure: MagicMock,
) -> None:
    """LoginError during session refresh triggers reauth."""
    await _async_setup(hass, mock_config_entry)
    mock_verisure.update_cookie.side_effect = AuthenticationError(
        "session expired", status_code=401
    )
    mock_verisure.login_cookie.side_effect = LoginError("login failed")

    await _async_trigger_coordinator_update(hass, mock_config_entry)

    assert mock_config_entry.state is ConfigEntryState.LOADED
    flows = hass.config_entries.flow.async_progress_by_handler(DOMAIN)
    assert len(flows) == 1
    assert flows[0]["context"]["source"] == "reauth"


async def test_update_session_refresh_transient(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_verisure: MagicMock,
) -> None:
    """Transient errors during session refresh keep the entry loaded."""
    await _async_setup(hass, mock_config_entry)
    mock_verisure.update_cookie.side_effect = AuthenticationError(
        "session expired", status_code=401
    )
    mock_verisure.login_cookie.side_effect = ResponseError(503, "server error")

    await _async_trigger_coordinator_update(hass, mock_config_entry)

    assert mock_config_entry.state is ConfigEntryState.LOADED
    assert not mock_config_entry.runtime_data.last_update_success


async def test_update_smartcam_imageseries(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_verisure: MagicMock,
) -> None:
    """Image series are parsed from the API response."""
    await _async_setup(hass, mock_config_entry)
    coordinator = mock_config_entry.runtime_data
    mock_verisure.request.return_value = {
        "data": {
            "ContentProviderMediaSearch": {
                "mediaSeriesList": [
                    {
                        "deviceMediaList": [
                            {"contentType": "IMAGE_JPEG", "id": "img-1"},
                            {"contentType": "VIDEO_MP4", "id": "vid-1"},
                        ]
                    }
                ]
            }
        }
    }

    coordinator.update_smartcam_imageseries()

    assert coordinator.imageseries == [{"contentType": "IMAGE_JPEG", "id": "img-1"}]


async def test_smartcam_capture(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_verisure: MagicMock,
) -> None:
    """Smartcam capture polls until the image is available."""
    await _async_setup(hass, mock_config_entry)
    coordinator = mock_config_entry.runtime_data
    mock_verisure.request.side_effect = [
        {"data": {"ContentProviderCaptureImageRequest": {"requestId": "req-1"}}},
        {
            "data": {
                "installation": {
                    "cameraContentProvider": {
                        "captureImageRequestStatus": {"mediaRequestStatus": "AVAILABLE"}
                    }
                }
            }
        },
    ]

    coordinator.smartcam_capture("cam-1")

    assert mock_verisure.camera_get_request_id.call_count == 1
    assert mock_verisure.camera_capture.call_count == 1
