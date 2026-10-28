"""The tests for the hassio component."""

from contextlib import AbstractContextManager, ExitStack as DefaultContext
from http import HTTPStatus
from unittest.mock import MagicMock, Mock, patch

from aiohttp.test_utils import TestClient
from aiohttp.web_exceptions import HTTPUnauthorized
import pytest
from pytest_homeassistant.common import MockUser

from homeassistant.auth.const import GROUP_ID_ADMIN, GROUP_ID_USER
from homeassistant.auth.providers import homeassistant as auth_ha
from homeassistant.auth.providers.homeassistant import InvalidAuth
from homeassistant.components.hassio.auth import HassIOBaseAuth
from homeassistant.components.http.const import DATA_SUPERVISOR_USER
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
        # No user is linked to the credentials, so no groups are reported
        assert await resp.json() == {"group_ids": []}


async def _link_user(
    hass: HomeAssistant,
    group_ids: list[str],
    *,
    is_owner: bool = False,
    is_active: bool = True,
) -> None:
    """Create a user with a password and link the credentials to it."""
    user = MockUser(
        is_owner=is_owner,
        is_active=is_active,
        groups=[await hass.auth.async_get_group(group_id) for group_id in group_ids],
    )
    provider = auth_ha.async_get_provider(hass)
    await provider.async_initialize()
    assert provider.data is not None
    provider.data.add_auth("test", "123456")
    credentials = await provider.async_get_or_create_credentials({"username": "test"})
    await hass.auth.async_link_user(user.add_to_auth_manager(hass.auth), credentials)


@pytest.mark.parametrize(
    ("group_ids", "is_owner", "expected"),
    [
        pytest.param([GROUP_ID_ADMIN], False, [GROUP_ID_ADMIN], id="admin"),
        pytest.param([GROUP_ID_USER], False, [GROUP_ID_USER], id="user"),
        pytest.param([], True, [GROUP_ID_ADMIN], id="owner_without_admin_group"),
    ],
)
async def test_auth_reports_group_ids(
    hass: HomeAssistant,
    hassio_client_supervisor: TestClient,
    group_ids: list[str],
    is_owner: bool,
    expected: list[str],
) -> None:
    """Test a successful login reports the group IDs of the user."""
    await _link_user(hass, group_ids, is_owner=is_owner)

    resp = await hassio_client_supervisor.post(
        "/api/hassio_auth",
        json={"username": "test", "password": "123456", "addon": "samba"},
    )

    assert resp.status == HTTPStatus.OK
    assert await resp.json() == {"group_ids": expected}


async def test_auth_refuses_inactive_user(
    hass: HomeAssistant, hassio_client_supervisor: TestClient
) -> None:
    """Test a deactivated user cannot log in through an app."""
    await _link_user(hass, [GROUP_ID_ADMIN], is_active=False)

    resp = await hassio_client_supervisor.post(
        "/api/hassio_auth",
        json={"username": "test", "password": "123456", "addon": "samba"},
    )

    assert resp.status == HTTPStatus.NOT_FOUND


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
    ("peername", "unix_socket", "expectation"),
    [
        # Unix socket transports report an empty string for peername. Before
        # the fix this raised IndexError on `peername[0]`.
        ("", True, DefaultContext()),
        # Defensive: a TCP transport with no peername at all should be
        # rejected, not crash.
        (None, False, pytest.raises(HTTPUnauthorized)),
    ],
)
@pytest.mark.usefixtures("hassio_stubs")
async def test_check_access_unix_socket_or_missing_peername(
    hass: HomeAssistant,
    peername: str | None,
    unix_socket: bool,
    expectation: AbstractContextManager,
) -> None:
    """Test _check_access handles Unix socket requests and missing peername."""
    user = hass.data.get(DATA_SUPERVISOR_USER)
    assert user is not None

    auth_view = HassIOBaseAuth(hass)
    request = MagicMock()
    request.transport.get_extra_info.return_value = peername
    request.__getitem__.return_value = user

    with (
        patch(
            "homeassistant.components.hassio.auth.is_supervisor_unix_socket_request",
            return_value=unix_socket,
        ),
        expectation,
    ):
        auth_view._check_access(request)


async def test_password_no_user(hassio_client_supervisor: TestClient) -> None:
    """Test changing password for invalid user."""
    resp = await hassio_client_supervisor.post(
        "/api/hassio_auth/password_reset",
        json={"username": "test", "password": "123456"},
    )

    # Check we got right response
    assert resp.status == HTTPStatus.NOT_FOUND
