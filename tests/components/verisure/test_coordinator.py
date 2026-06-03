"""Tests for the Verisure coordinator."""

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

from homeassistant.components.verisure.coordinator import VerisureDataUpdateCoordinator
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.update_coordinator import UpdateFailed

from tests.common import MockConfigEntry

OVERVIEW = [
    {
        "data": {
            "installation": {
                "armState": {"status": "DISARMED"},
                "broadband": [{"status": "ONLINE"}],
                "cameras": [
                    {"device": {"deviceLabel": "cam-1"}, "status": "AVAILABLE"}
                ],
                "climates": [
                    {"device": {"deviceLabel": "climate-1"}, "temperature": 21}
                ],
                "doorWindows": [
                    {"device": {"deviceLabel": "door-1"}, "status": "CLOSED"}
                ],
                "smartLocks": [
                    {"device": {"deviceLabel": "lock-1"}, "status": "LOCKED"}
                ],
                "smartplugs": [
                    {"device": {"deviceLabel": "plug-1"}, "status": "on"}
                ],
            }
        }
    }
]


@pytest.fixture
def mock_verisure_session() -> MagicMock:
    """Return a mocked Verisure session."""
    with patch(
        "homeassistant.components.verisure.coordinator.Verisure", autospec=True
    ) as mock_cls:
        session = mock_cls.return_value
        session.request.return_value = OVERVIEW
        yield session


@pytest.fixture
def coordinator(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_verisure_session: MagicMock,
) -> VerisureDataUpdateCoordinator:
    """Return a coordinator with a mocked Verisure session."""
    return VerisureDataUpdateCoordinator(hass, mock_config_entry)


@pytest.mark.parametrize(
    "exc",
    [
        RequestError("network"),
        ResponseError(503, "server error"),
        RateLimitError("rate limited"),
    ],
)
async def test_async_login_transient(
    coordinator: VerisureDataUpdateCoordinator,
    mock_verisure_session: MagicMock,
    exc: Exception,
) -> None:
    """Transient failures during login return False instead of reauth."""
    mock_verisure_session.login_cookie.side_effect = exc

    assert await coordinator.async_login() is False
    mock_verisure_session.set_giid.assert_not_called()


async def test_async_login_authentication_error(
    coordinator: VerisureDataUpdateCoordinator,
    mock_verisure_session: MagicMock,
) -> None:
    """Invalid credentials raise ConfigEntryAuthFailed."""
    mock_verisure_session.login_cookie.side_effect = AuthenticationError(
        "auth failed", status_code=401
    )

    with pytest.raises(ConfigEntryAuthFailed):
        await coordinator.async_login()


async def test_async_login_success(
    coordinator: VerisureDataUpdateCoordinator,
    mock_verisure_session: MagicMock,
) -> None:
    """Successful cookie login sets giid and returns True."""
    assert await coordinator.async_login() is True
    mock_verisure_session.login_cookie.assert_called_once()
    mock_verisure_session.set_giid.assert_called_once()


async def test_async_login_cookie_read_uses_password_login(
    coordinator: VerisureDataUpdateCoordinator,
    mock_verisure_session: MagicMock,
) -> None:
    """Unreadable cookie file falls back to password login."""
    mock_verisure_session.login_cookie.side_effect = CookieReadError(
        "Failed to read cookie"
    )

    assert await coordinator.async_login() is True
    mock_verisure_session.login.assert_called_once()
    mock_verisure_session.set_giid.assert_called_once()


async def test_async_login_cookie_read_transient_returns_false(
    coordinator: VerisureDataUpdateCoordinator,
    mock_verisure_session: MagicMock,
) -> None:
    """Transient password login after cookie read returns False."""
    mock_verisure_session.login_cookie.side_effect = CookieReadError(
        "Failed to read cookie"
    )
    mock_verisure_session.login.side_effect = RequestError("offline")

    assert await coordinator.async_login() is False
    mock_verisure_session.set_giid.assert_not_called()


async def test_async_login_cookie_read_authentication_error(
    coordinator: VerisureDataUpdateCoordinator,
    mock_verisure_session: MagicMock,
) -> None:
    """Authentication failure after cookie read raises ConfigEntryAuthFailed."""
    mock_verisure_session.login_cookie.side_effect = CookieReadError(
        "Failed to read cookie"
    )
    mock_verisure_session.login.side_effect = AuthenticationError(
        "bad credentials", status_code=401
    )

    with pytest.raises(
        ConfigEntryAuthFailed,
        match="re-authentication failed after cookie could not be read",
    ):
        await coordinator.async_login()


async def test_async_login_non_transient_verisure_error_returns_false(
    coordinator: VerisureDataUpdateCoordinator,
    mock_verisure_session: MagicMock,
) -> None:
    """Unexpected Verisure errors during login return False."""
    mock_verisure_session.login_cookie.side_effect = VerisureBaseError("unknown")

    assert await coordinator.async_login() is False


async def test_async_update_data_authentication_refreshes_session(
    coordinator: VerisureDataUpdateCoordinator,
    mock_verisure_session: MagicMock,
) -> None:
    """Expired session cookie triggers login_cookie recovery."""
    mock_verisure_session.update_cookie.side_effect = AuthenticationError(
        "session expired", status_code=401
    )

    data = await coordinator._async_update_data()

    assert data["alarm"] == {"status": "DISARMED"}
    assert data["cameras"] == {
        "cam-1": {"device": {"deviceLabel": "cam-1"}, "status": "AVAILABLE"}
    }
    assert data["locks"] == {
        "lock-1": {"device": {"deviceLabel": "lock-1"}, "status": "LOCKED"}
    }
    mock_verisure_session.login_cookie.assert_called_once()
    mock_verisure_session.request.assert_called_once()


async def test_async_update_data_cookie_read_uses_password_login(
    coordinator: VerisureDataUpdateCoordinator,
    mock_verisure_session: MagicMock,
) -> None:
    """Corrupt cookie during refresh re-authenticates with password."""
    mock_verisure_session.update_cookie.side_effect = CookieReadError(
        "Failed to read cookie"
    )

    data = await coordinator._async_update_data()

    assert data["alarm"] == {"status": "DISARMED"}
    mock_verisure_session.login.assert_called_once()


@pytest.mark.parametrize(
    ("exc", "match"),
    [
        (RequestError("offline"), "Verisure unreachable"),
        (ResponseError(503, "server error"), "Verisure unreachable"),
        (RateLimitError("rate limited"), "Verisure rate limited"),
    ],
)
async def test_async_update_data_transient_update_cookie_raises_update_failed(
    coordinator: VerisureDataUpdateCoordinator,
    mock_verisure_session: MagicMock,
    exc: Exception,
    match: str,
) -> None:
    """Transient failures during cookie refresh raise UpdateFailed."""
    mock_verisure_session.update_cookie.side_effect = exc

    with pytest.raises(UpdateFailed, match=match):
        await coordinator._async_update_data()


async def test_async_update_data_login_error_refreshes_session(
    coordinator: VerisureDataUpdateCoordinator,
    mock_verisure_session: MagicMock,
) -> None:
    """Recoverable login errors after update_cookie retries trigger session refresh."""
    mock_verisure_session.update_cookie.side_effect = LoginError("token refresh failed")

    data = await coordinator._async_update_data()

    assert data["alarm"] == {"status": "DISARMED"}
    mock_verisure_session.login_cookie.assert_called_once()


async def test_async_login_login_error_raises_auth_failed(
    coordinator: VerisureDataUpdateCoordinator,
    mock_verisure_session: MagicMock,
) -> None:
    """Generic login errors raise ConfigEntryAuthFailed."""
    mock_verisure_session.login_cookie.side_effect = LoginError("login failed")

    with pytest.raises(ConfigEntryAuthFailed, match="Credentials expired"):
        await coordinator.async_login()


async def test_refresh_session_login_cookie_authentication_error(
    coordinator: VerisureDataUpdateCoordinator,
    mock_verisure_session: MagicMock,
) -> None:
    """Authentication failure during session refresh raises ConfigEntryAuthFailed."""
    mock_verisure_session.update_cookie.side_effect = AuthenticationError(
        "session expired", status_code=401
    )
    mock_verisure_session.login_cookie.side_effect = AuthenticationError(
        "invalid session", status_code=403
    )

    with pytest.raises(ConfigEntryAuthFailed, match="authentication rejected"):
        await coordinator._async_update_data()


async def test_refresh_session_cookie_read_password_login_auth_error(
    coordinator: VerisureDataUpdateCoordinator,
    mock_verisure_session: MagicMock,
) -> None:
    """Authentication failure after cookie-read password login raises ConfigEntryAuthFailed."""
    mock_verisure_session.update_cookie.side_effect = AuthenticationError(
        "session expired", status_code=401
    )
    mock_verisure_session.login_cookie.side_effect = CookieReadError(
        "Failed to read cookie"
    )
    mock_verisure_session.login.side_effect = AuthenticationError(
        "bad credentials", status_code=401
    )

    with pytest.raises(
        ConfigEntryAuthFailed,
        match="re-authentication failed after cookie could not be read",
    ):
        await coordinator._async_update_data()


async def test_update_data_cookie_read_password_login_transient(
    coordinator: VerisureDataUpdateCoordinator,
    mock_verisure_session: MagicMock,
) -> None:
    """Transient failure during cookie-read password login raises UpdateFailed."""
    mock_verisure_session.update_cookie.side_effect = CookieReadError(
        "Failed to read cookie"
    )
    mock_verisure_session.login.side_effect = RequestError("offline")

    with pytest.raises(UpdateFailed, match="transient"):
        await coordinator._async_update_data()


async def test_update_data_cookie_read_password_login_error(
    coordinator: VerisureDataUpdateCoordinator,
    mock_verisure_session: MagicMock,
) -> None:
    """LoginError during cookie-read password login raises ConfigEntryAuthFailed."""
    mock_verisure_session.update_cookie.side_effect = CookieReadError(
        "Failed to read cookie"
    )
    mock_verisure_session.login.side_effect = LoginError("login failed")

    with pytest.raises(
        ConfigEntryAuthFailed,
        match="re-authentication failed after cookie could not be read",
    ):
        await coordinator._async_update_data()


async def test_update_cookie_generic_verisure_error(
    coordinator: VerisureDataUpdateCoordinator,
    mock_verisure_session: MagicMock,
) -> None:
    """Unexpected errors during cookie refresh raise UpdateFailed."""
    mock_verisure_session.update_cookie.side_effect = VerisureBaseError("unknown")

    with pytest.raises(UpdateFailed, match="Unable to update cookie"):
        await coordinator._async_update_data()


async def test_overview_request_raises_update_failed(
    coordinator: VerisureDataUpdateCoordinator,
    mock_verisure_session: MagicMock,
) -> None:
    """Failures while fetching overview raise UpdateFailed."""
    mock_verisure_session.request.side_effect = RequestError("offline")

    with pytest.raises(UpdateFailed, match="Could not read overview"):
        await coordinator._async_update_data()


async def test_refresh_session_cookie_read_success(
    coordinator: VerisureDataUpdateCoordinator,
    mock_verisure_session: MagicMock,
) -> None:
    """Cookie read during session refresh falls back to password login."""
    mock_verisure_session.update_cookie.side_effect = AuthenticationError(
        "session expired", status_code=401
    )
    mock_verisure_session.login_cookie.side_effect = CookieReadError(
        "Failed to read cookie"
    )

    data = await coordinator._async_update_data()

    assert data["alarm"] == {"status": "DISARMED"}
    mock_verisure_session.login.assert_called_once()


async def test_refresh_session_login_error_on_login_cookie(
    coordinator: VerisureDataUpdateCoordinator,
    mock_verisure_session: MagicMock,
) -> None:
    """LoginError during session refresh raises ConfigEntryAuthFailed."""
    mock_verisure_session.update_cookie.side_effect = AuthenticationError(
        "session expired", status_code=401
    )
    mock_verisure_session.login_cookie.side_effect = LoginError("login failed")

    with pytest.raises(ConfigEntryAuthFailed, match="Credentials expired"):
        await coordinator._async_update_data()


async def test_refresh_session_transient_on_login_cookie(
    coordinator: VerisureDataUpdateCoordinator,
    mock_verisure_session: MagicMock,
) -> None:
    """Transient errors during session refresh raise UpdateFailed."""
    mock_verisure_session.update_cookie.side_effect = AuthenticationError(
        "session expired", status_code=401
    )
    mock_verisure_session.login_cookie.side_effect = ResponseError(503, "server error")

    with pytest.raises(UpdateFailed, match="transient"):
        await coordinator._async_update_data()


async def test_refresh_session_generic_error_on_login_cookie(
    coordinator: VerisureDataUpdateCoordinator,
    mock_verisure_session: MagicMock,
) -> None:
    """Unexpected errors during session refresh raise UpdateFailed."""
    mock_verisure_session.update_cookie.side_effect = AuthenticationError(
        "session expired", status_code=401
    )
    mock_verisure_session.login_cookie.side_effect = VerisureBaseError("unknown")

    with pytest.raises(UpdateFailed, match="Could not log in to Verisure"):
        await coordinator._async_update_data()


def test_update_smartcam_imageseries(
    coordinator: VerisureDataUpdateCoordinator,
    mock_verisure_session: MagicMock,
) -> None:
    """Image series are parsed from the API response."""
    mock_verisure_session.request.return_value = {
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


def test_smartcam_capture(
    coordinator: VerisureDataUpdateCoordinator,
    mock_verisure_session: MagicMock,
) -> None:
    """Smartcam capture polls until the image is available."""
    mock_verisure_session.request.side_effect = [
        {
            "data": {
                "ContentProviderCaptureImageRequest": {"requestId": "req-1"}
            }
        },
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

    assert mock_verisure_session.camera_get_request_id.call_count == 1
    assert mock_verisure_session.camera_capture.call_count == 1
