"""Tests for the Verisure coordinator."""

from unittest.mock import MagicMock, patch

import pytest
from verisure import (
    AuthenticationError,
    CookieReadError,
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
                "broadband": [],
                "cameras": [],
                "climates": [],
                "doorWindows": [],
                "smartLocks": [],
                "smartplugs": [],
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
