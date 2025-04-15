"""The tests for the hassio component."""

from http import HTTPStatus
from unittest.mock import Mock, patch

from aiohttp.test_utils import TestClient

from homeassistant.auth.providers.homeassistant import InvalidAuth


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


async def test_password_no_user(hassio_client_supervisor: TestClient) -> None:
    """Test changing password for invalid user."""
    resp = await hassio_client_supervisor.post(
        "/api/hassio_auth/password_reset",
        json={"username": "test", "password": "123456"},
    )

    # Check we got right response
    assert resp.status == HTTPStatus.NOT_FOUND
