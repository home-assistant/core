"""The tests for the hassio component."""

from http import HTTPStatus
from unittest.mock import MagicMock, Mock, patch

from aiohttp.test_utils import TestClient
from aiohttp.web_exceptions import HTTPUnauthorized
import pytest

from homeassistant.auth.providers.homeassistant import InvalidAuth
from homeassistant.components.hassio.auth import HassIOBaseAuth
from homeassistant.components.hassio.const import DATA_CONFIG_STORE
from homeassistant.components.http import KEY_HASS_USER
from homeassistant.core import HomeAssistant


async def test_auth_success(hassio_client_supervisor: TestClient) -> None:
    """Test no auth needed for ."""
    with patch(
        "homeassistant.auth.providers.homeassistant."
        "HassAuthProvider.async_validate_login",
    ) as mock_login:
        resp = await hassio_client_supervisor.post(
            "/api/hassio_auth",
            json={"username": "test", "password": "123456", "addon": "samba"},
        )

        # Check we got right response
        assert resp.status == HTTPStatus.OK
        mock_login.assert_called_with("test", "123456")


async def test_auth_fails_no_supervisor(hassio_client: TestClient) -> None:
    """Test if only supervisor can access."""
    with patch(
        "homeassistant.auth.providers.homeassistant."
        "HassAuthProvider.async_validate_login",
    ) as mock_login:
        resp = await hassio_client.post(
            "/api/hassio_auth",
            json={"username": "test", "password": "123456", "addon": "samba"},
        )

        # Check we got right response
        assert resp.status == HTTPStatus.UNAUTHORIZED
        assert not mock_login.called


async def test_auth_fails_no_auth(hassio_noauth_client: TestClient) -> None:
    """Test if only supervisor can access."""
    with patch(
        "homeassistant.auth.providers.homeassistant."
        "HassAuthProvider.async_validate_login",
    ) as mock_login:
        resp = await hassio_noauth_client.post(
            "/api/hassio_auth",
            json={"username": "test", "password": "123456", "addon": "samba"},
        )

        # Check we got right response
        assert resp.status == HTTPStatus.UNAUTHORIZED
        assert not mock_login.called


async def test_login_error(hassio_client_supervisor: TestClient) -> None:
    """Test no auth needed for error."""
    with patch(
        "homeassistant.auth.providers.homeassistant."
        "HassAuthProvider.async_validate_login",
        Mock(side_effect=InvalidAuth()),
    ) as mock_login:
        resp = await hassio_client_supervisor.post(
            "/api/hassio_auth",
            json={"username": "test", "password": "123456", "addon": "samba"},
        )

        # Check we got right response
        assert resp.status == HTTPStatus.NOT_FOUND
        mock_login.assert_called_with("test", "123456")


async def test_login_no_data(hassio_client_supervisor: TestClient) -> None:
    """Test auth with no data -> error."""
    with patch(
        "homeassistant.auth.providers.homeassistant."
        "HassAuthProvider.async_validate_login",
        Mock(side_effect=InvalidAuth()),
    ) as mock_login:
        resp = await hassio_client_supervisor.post("/api/hassio_auth")

        # Check we got right response
        assert resp.status == HTTPStatus.BAD_REQUEST
        assert not mock_login.called


async def test_login_no_username(hassio_client_supervisor: TestClient) -> None:
    """Test auth with no username in data -> error."""
    with patch(
        "homeassistant.auth.providers.homeassistant."
        "HassAuthProvider.async_validate_login",
        Mock(side_effect=InvalidAuth()),
    ) as mock_login:
        resp = await hassio_client_supervisor.post(
            "/api/hassio_auth", json={"password": "123456", "addon": "samba"}
        )

        # Check we got right response
        assert resp.status == HTTPStatus.BAD_REQUEST
        assert not mock_login.called


async def test_login_success_extra(hassio_client_supervisor: TestClient) -> None:
    """Test auth with extra data."""
    with patch(
        "homeassistant.auth.providers.homeassistant."
        "HassAuthProvider.async_validate_login",
    ) as mock_login:
        resp = await hassio_client_supervisor.post(
            "/api/hassio_auth",
            json={
                "username": "test",
                "password": "123456",
                "addon": "samba",
                "path": "/share",
            },
        )

        # Check we got right response
        assert resp.status == HTTPStatus.OK
        mock_login.assert_called_with("test", "123456")


async def test_password_success(hassio_client_supervisor: TestClient) -> None:
    """Test no auth needed for ."""
    with patch(
        "homeassistant.auth.providers.homeassistant."
        "HassAuthProvider.async_change_password",
    ) as mock_change:
        resp = await hassio_client_supervisor.post(
            "/api/hassio_auth/password_reset",
            json={"username": "test", "password": "123456"},
        )

        # Check we got right response
        assert resp.status == HTTPStatus.OK
        mock_change.assert_called_with("test", "123456")


async def test_password_fails_no_supervisor(hassio_client: TestClient) -> None:
    """Test if only supervisor can access."""
    resp = await hassio_client.post(
        "/api/hassio_auth/password_reset",
        json={"username": "test", "password": "123456"},
    )

    # Check we got right response
    assert resp.status == HTTPStatus.UNAUTHORIZED


async def test_password_fails_no_auth(hassio_noauth_client: TestClient) -> None:
    """Test if only supervisor can access."""
    resp = await hassio_noauth_client.post(
        "/api/hassio_auth/password_reset",
        json={"username": "test", "password": "123456"},
    )

    # Check we got right response
    assert resp.status == HTTPStatus.UNAUTHORIZED


@pytest.mark.parametrize(
    ("peername", "unix_socket"),
    [
        # Unix socket transports report an empty string for peername. Before
        # the fix this raised IndexError on `peername[0]`.
        ("", True),
        # Defensive: a TCP transport with no peername at all should be
        # rejected, not crash.
        (None, False),
    ],
)
async def test_check_access_unix_socket_or_missing_peername(
    hass: HomeAssistant,
    hassio_stubs: None,
    peername: str | None,
    unix_socket: bool,
) -> None:
    """Test _check_access handles Unix socket requests and missing peername."""
    hassio_user_id = hass.data[DATA_CONFIG_STORE].data.hassio_user
    assert hassio_user_id is not None
    user = await hass.auth.async_get_user(hassio_user_id)
    assert user is not None

    auth_view = HassIOBaseAuth(hass, user)

    request = MagicMock()
    request.transport.get_extra_info.return_value = peername
    request.__getitem__.side_effect = lambda key: user if key is KEY_HASS_USER else None

    with patch(
        "homeassistant.components.hassio.auth.is_supervisor_unix_socket_request",
        return_value=unix_socket,
    ):
        if unix_socket:
            auth_view._check_access(request)
        else:
            with pytest.raises(HTTPUnauthorized):
                auth_view._check_access(request)


async def test_password_no_user(hassio_client_supervisor: TestClient) -> None:
    """Test changing password for invalid user."""
    resp = await hassio_client_supervisor.post(
        "/api/hassio_auth/password_reset",
        json={"username": "test", "password": "123456"},
    )

    # Check we got right response
    assert resp.status == HTTPStatus.NOT_FOUND
