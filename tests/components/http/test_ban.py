"""The tests for the Home Assistant HTTP component."""
from http import HTTPStatus

# pylint: disable=protected-access
from ipaddress import ip_address
import os
from unittest.mock import Mock, mock_open, patch

from aiohttp import web
from aiohttp.web_exceptions import HTTPUnauthorized
from aiohttp.web_middlewares import middleware
import pytest

import homeassistant.components.http as http
from homeassistant.components.http import KEY_AUTHENTICATED
from homeassistant.components.http.ban import (
    IP_BANS_FILE,
    KEY_BAN_MANAGER,
    KEY_FAILED_LOGIN_ATTEMPTS,
    IpBanManager,
    setup_bans,
)
from homeassistant.components.http.view import request_handler_factory
from homeassistant.exceptions import HomeAssistantError
from homeassistant.setup import async_setup_component

from . import mock_real_ip

SUPERVISOR_IP = "1.2.3.4"
BANNED_IPS = ["200.201.202.203", "100.64.0.2"]
BANNED_IPS_WITH_SUPERVISOR = BANNED_IPS + [SUPERVISOR_IP]


@pytest.fixture(name="hassio_env")
def hassio_env_fixture():
    """Fixture to inject hassio env."""
    with patch.dict(os.environ, {"SUPERVISOR": "127.0.0.1"}), patch(
        "homeassistant.components.hassio.HassIO.is_connected",
        return_value={"result": "ok", "data": {}},
    ), patch.dict(os.environ, {"SUPERVISOR_TOKEN": "123456"}):
        yield


@pytest.fixture(autouse=True)
def gethostbyaddr_mock():
    """Fixture to mock out I/O on getting host by address."""
    with patch(
        "homeassistant.components.http.ban.gethostbyaddr",
        return_value=("example.com", ["0.0.0.0.in-addr.arpa"], ["0.0.0.0"]),
    ):
        yield


async def test_access_from_banned_ip(hass, aiohttp_client):
    """Test accessing to server from banned IP. Both trusted and not."""
    app = web.Application()
    app["hass"] = hass
    setup_bans(hass, app, 5)
    set_real_ip = mock_real_ip(app)

    with patch(
        "homeassistant.components.http.ban.load_yaml_config_file",
        return_value={
            banned_ip: {"banned_at": "2016-11-16T19:20:03"} for banned_ip in BANNED_IPS
        },
    ):
        client = await aiohttp_client(app)

    for remote_addr in BANNED_IPS:
        set_real_ip(remote_addr)
        resp = await client.get("/")
        assert resp.status == HTTPStatus.FORBIDDEN


async def test_access_from_banned_ip_with_partially_broken_yaml_file(
    hass, aiohttp_client, caplog
):
    """Test accessing to server from banned IP. Both trusted and not.

    We inject some garbage into the yaml file to make sure it can
    still load the bans.
    """
    app = web.Application()
    app["hass"] = hass
    setup_bans(hass, app, 5)
    set_real_ip = mock_real_ip(app)

    data = {banned_ip: {"banned_at": "2016-11-16T19:20:03"} for banned_ip in BANNED_IPS}
    data["5.3.3.3"] = {"banned_at": "garbage"}

    with patch(
        "homeassistant.components.http.ban.load_yaml_config_file",
        return_value=data,
    ):
        client = await aiohttp_client(app)

    for remote_addr in BANNED_IPS:
        set_real_ip(remote_addr)
        resp = await client.get("/")
        assert resp.status == HTTPStatus.FORBIDDEN

    # Ensure garbage data is ignored
    set_real_ip("5.3.3.3")
    resp = await client.get("/")
    assert resp.status == HTTPStatus.NOT_FOUND

    assert "Failed to load IP ban" in caplog.text


async def test_no_ip_bans_file(hass, aiohttp_client):
    """Test no ip bans file."""
    app = web.Application()
    app["hass"] = hass
    setup_bans(hass, app, 5)
    set_real_ip = mock_real_ip(app)

    with patch(
        "homeassistant.components.http.ban.load_yaml_config_file",
        side_effect=FileNotFoundError,
    ):
        client = await aiohttp_client(app)

    set_real_ip("4.3.2.1")
    resp = await client.get("/")
    assert resp.status == HTTPStatus.NOT_FOUND


async def test_failure_loading_ip_bans_file(hass, aiohttp_client):
    """Test failure loading ip bans file."""
    app = web.Application()
    app["hass"] = hass
    setup_bans(hass, app, 5)
    set_real_ip = mock_real_ip(app)

    with patch(
        "homeassistant.components.http.ban.load_yaml_config_file",
        side_effect=HomeAssistantError,
    ):
        client = await aiohttp_client(app)

    set_real_ip("4.3.2.1")
    resp = await client.get("/")
    assert resp.status == HTTPStatus.NOT_FOUND


async def test_ip_ban_manager_never_started(hass, aiohttp_client, caplog):
    """Test we handle the ip ban manager not being started."""
    app = web.Application()
    app["hass"] = hass
    setup_bans(hass, app, 5)
    set_real_ip = mock_real_ip(app)

    with patch(
        "homeassistant.components.http.ban.load_yaml_config_file",
        side_effect=FileNotFoundError,
    ):
        client = await aiohttp_client(app)

    # Mock the manager never being started
    del app[KEY_BAN_MANAGER]

    set_real_ip("4.3.2.1")
    resp = await client.get("/")
    assert resp.status == HTTPStatus.NOT_FOUND
    assert "IP Ban middleware loaded but banned IPs not loaded" in caplog.text


@pytest.mark.parametrize(
    "remote_addr, bans, status",
    list(
        zip(
            BANNED_IPS_WITH_SUPERVISOR,
            [1, 1, 0],
            [HTTPStatus.FORBIDDEN, HTTPStatus.FORBIDDEN, HTTPStatus.UNAUTHORIZED],
        )
    ),
)
async def test_access_from_supervisor_ip(
    remote_addr, bans, status, hass, aiohttp_client, hassio_env
):
    """Test accessing to server from supervisor IP."""
    app = web.Application()
    app["hass"] = hass

    async def unauth_handler(request):
        """Return a mock web response."""
        raise HTTPUnauthorized

    app.router.add_get("/", unauth_handler)
    setup_bans(hass, app, 1)
    mock_real_ip(app)(remote_addr)

    with patch(
        "homeassistant.components.http.ban.load_yaml_config_file",
        return_value={},
    ):
        client = await aiohttp_client(app)

    manager: IpBanManager = app[KEY_BAN_MANAGER]

    assert await async_setup_component(hass, "hassio", {"hassio": {}})

    m_open = mock_open()

    with patch.dict(os.environ, {"SUPERVISOR": SUPERVISOR_IP}), patch(
        "homeassistant.components.http.ban.open", m_open, create=True
    ):
        resp = await client.get("/")
        assert resp.status == HTTPStatus.UNAUTHORIZED
        assert len(manager.ip_bans_lookup) == bans
        assert m_open.call_count == bans

        # second request should be forbidden if banned
        resp = await client.get("/")
        assert resp.status == status
        assert len(manager.ip_bans_lookup) == bans


async def test_ban_middleware_not_loaded_by_config(hass):
    """Test accessing to server from banned IP when feature is off."""
    with patch("homeassistant.components.http.setup_bans") as mock_setup:
        await async_setup_component(
            hass, "http", {"http": {http.CONF_IP_BAN_ENABLED: False}}
        )

    assert len(mock_setup.mock_calls) == 0


async def test_ban_middleware_loaded_by_default(hass):
    """Test accessing to server from banned IP when feature is off."""
    with patch("homeassistant.components.http.setup_bans") as mock_setup:
        await async_setup_component(hass, "http", {"http": {}})

    assert len(mock_setup.mock_calls) == 1


async def test_ip_bans_file_creation(hass, aiohttp_client, caplog):
    """Testing if banned IP file created."""
    app = web.Application()
    app["hass"] = hass

    async def unauth_handler(request):
        """Return a mock web response."""
        raise HTTPUnauthorized

    app.router.add_get("/example", unauth_handler)
    setup_bans(hass, app, 2)
    mock_real_ip(app)("200.201.202.204")

    with patch(
        "homeassistant.components.http.ban.load_yaml_config_file",
        return_value={
            banned_ip: {"banned_at": "2016-11-16T19:20:03"} for banned_ip in BANNED_IPS
        },
    ):
        client = await aiohttp_client(app)

    manager: IpBanManager = app[KEY_BAN_MANAGER]
    m_open = mock_open()

    with patch("homeassistant.components.http.ban.open", m_open, create=True):
        resp = await client.get("/example")
        assert resp.status == HTTPStatus.UNAUTHORIZED
        assert len(manager.ip_bans_lookup) == len(BANNED_IPS)
        assert m_open.call_count == 0

        resp = await client.get("/example")
        assert resp.status == HTTPStatus.UNAUTHORIZED
        assert len(manager.ip_bans_lookup) == len(BANNED_IPS) + 1
        m_open.assert_called_once_with(
            hass.config.path(IP_BANS_FILE), "a", encoding="utf8"
        )

        resp = await client.get("/example")
        assert resp.status == HTTPStatus.FORBIDDEN
        assert m_open.call_count == 1

        assert (
            len(notifications := hass.states.async_all("persistent_notification")) == 2
        )
        assert (
            notifications[0].attributes["message"]
            == "Login attempt or request with invalid authentication from example.com (200.201.202.204). See the log for details."
        )

        assert (
            "Login attempt or request with invalid authentication from example.com (200.201.202.204). Requested URL: '/example'."
            in caplog.text
        )


async def test_failed_login_attempts_counter(hass, aiohttp_client):
    """Testing if failed login attempts counter increased."""
    app = web.Application()
    app["hass"] = hass

    async def auth_handler(request):
        """Return 200 status code."""
        return None, 200

    app.router.add_get(
        "/auth_true", request_handler_factory(Mock(requires_auth=True), auth_handler)
    )
    app.router.add_get(
        "/auth_false", request_handler_factory(Mock(requires_auth=True), auth_handler)
    )
    app.router.add_get(
        "/", request_handler_factory(Mock(requires_auth=False), auth_handler)
    )

    setup_bans(hass, app, 5)
    remote_ip = ip_address("200.201.202.204")
    mock_real_ip(app)("200.201.202.204")

    @middleware
    async def mock_auth(request, handler):
        """Mock auth middleware."""
        if "auth_true" in request.path:
            request[KEY_AUTHENTICATED] = True
        else:
            request[KEY_AUTHENTICATED] = False
        return await handler(request)

    app.middlewares.append(mock_auth)

    client = await aiohttp_client(app)

    resp = await client.get("/auth_false")
    assert resp.status == HTTPStatus.UNAUTHORIZED
    assert app[KEY_FAILED_LOGIN_ATTEMPTS][remote_ip] == 1

    resp = await client.get("/auth_false")
    assert resp.status == HTTPStatus.UNAUTHORIZED
    assert app[KEY_FAILED_LOGIN_ATTEMPTS][remote_ip] == 2

    resp = await client.get("/")
    assert resp.status == HTTPStatus.OK
    assert app[KEY_FAILED_LOGIN_ATTEMPTS][remote_ip] == 2

    # This used to check that with trusted networks we reset login attempts
    # We no longer support trusted networks.
    resp = await client.get("/auth_true")
    assert resp.status == HTTPStatus.OK
    assert app[KEY_FAILED_LOGIN_ATTEMPTS][remote_ip] == 2
