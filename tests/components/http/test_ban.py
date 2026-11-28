"""The tests for the Home Assistant HTTP component."""

from datetime import timedelta
from http import HTTPStatus
from ipaddress import ip_address
import logging
import os
from pathlib import Path
from socket import gaierror, herror
import threading
from typing import NoReturn
from unittest.mock import AsyncMock, Mock, mock_open, patch

from aiohttp import web
from aiohttp.test_utils import TestClient
from aiohttp.web_exceptions import HTTPUnauthorized
from aiohttp.web_middlewares import middleware
from freezegun.api import FrozenDateTimeFactory
import pytest
from pytest_homeassistant.common import async_get_persistent_notifications
from pytest_homeassistant.typing import ClientSessionGenerator

from homeassistant.components import http
from homeassistant.components.http import DOMAIN
from homeassistant.components.http.ban import (
    IP_BANS_FILE,
    KEY_BAN_MANAGER,
    KEY_FAILED_LOGIN_ATTEMPTS,
    process_success_login,
    setup_bans,
)
from homeassistant.components.http.view import request_handler_factory
from homeassistant.config import load_yaml_config_file
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.http import KEY_AUTHENTICATED, KEY_HASS
from homeassistant.setup import async_setup_component

from tests.test_util import mock_real_ip

SUPERVISOR_IP = "1.2.3.4"
BANNED_IPS = ["200.201.202.203", "100.64.0.2"]
BANNED_IPS_WITH_SUPERVISOR = [*BANNED_IPS, SUPERVISOR_IP]


@pytest.fixture(name="hassio_env")
def hassio_env_fixture(supervisor_is_connected: AsyncMock):
    """Fixture to inject hassio env."""
    with (
        patch.dict(os.environ, {"SUPERVISOR": "127.0.0.1"}),
        patch.dict(os.environ, {"SUPERVISOR_TOKEN": "123456"}),
    ):
        yield


@pytest.fixture(autouse=True)
def gethostbyaddr_mock():
    """Fixture to mock out I/O on getting host by address."""
    with patch(
        "homeassistant.components.http.ban.gethostbyaddr",
        return_value=("example.com", ["0.0.0.0.in-addr.arpa"], ["0.0.0.0"]),
    ):
        yield


async def test_access_from_banned_ip(
    hass: HomeAssistant, aiohttp_client: ClientSessionGenerator
) -> None:
    """Test accessing to server from banned IP. Both trusted and not."""
    app = web.Application()
    app[KEY_HASS] = hass
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
    hass: HomeAssistant,
    aiohttp_client: ClientSessionGenerator,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test loading IP bans from a partially broken YAML file."""
    app = web.Application()
    app[KEY_HASS] = hass
    setup_bans(hass, app, 5)
    set_real_ip = mock_real_ip(app)

    data = {
        BANNED_IPS[0]: {"banned_at": "2016-11-16T19:20:03"},
        "5.3.3.3": {"banned_at": "garbage"},
        "5.3.3.4": {},
        "5.3.3.5": None,
        BANNED_IPS[1]: {"banned_at": "2016-11-16T19:20:03"},
    }

    with patch(
        "homeassistant.components.http.ban.load_yaml_config_file",
        return_value=data,
    ):
        client = await aiohttp_client(app)

    for remote_addr in (*BANNED_IPS, "5.3.3.4"):
        set_real_ip(remote_addr)
        resp = await client.get("/")
        assert resp.status == HTTPStatus.FORBIDDEN

    # Ensure malformed data is ignored
    for remote_addr in ("5.3.3.3", "5.3.3.5"):
        set_real_ip(remote_addr)
        resp = await client.get("/")
        assert resp.status == HTTPStatus.NOT_FOUND

    assert caplog.text.count("Failed to load IP ban") == 2


async def test_access_from_banned_ip_with_invalid_ip_entry(
    hass: HomeAssistant,
    aiohttp_client: ClientSessionGenerator,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test that invalid IP addresses in ban file are skipped gracefully.

    An invalid IP entry (e.g., with typo like "Eo128.199.160.243") should
    be logged as an error and skipped, allowing valid bans to still load.
    The test ensures that valid IPs after invalid ones are still processed.
    """
    app = web.Application()
    app[KEY_HASS] = hass
    setup_bans(hass, app, 5)
    set_real_ip = mock_real_ip(app)

    # Invalid IPs interspersed between valid ones to ensure continue works
    data = {
        "Eo128.199.160.243": {"banned_at": "2024-07-06T14:07:46"},
        BANNED_IPS[0]: {"banned_at": "2016-11-16T19:20:03"},
        "invalidip": {"banned_at": "2024-07-06T14:07:46"},
        BANNED_IPS[1]: {"banned_at": "2016-11-16T19:20:03"},
    }

    with patch(
        "homeassistant.components.http.ban.load_yaml_config_file",
        return_value=data,
    ):
        client = await aiohttp_client(app)

    # Verify exactly 2 valid IPs were loaded (invalid ones skipped)
    manager = app[KEY_BAN_MANAGER]
    assert len(manager.ip_bans_lookup) == len(BANNED_IPS)

    # Valid banned IPs should still be blocked (even though they came after invalid
    # ones)
    for remote_addr in BANNED_IPS:
        set_real_ip(remote_addr)
        resp = await client.get("/")
        assert resp.status == HTTPStatus.FORBIDDEN

    # Non-banned IP should have access
    set_real_ip("192.168.1.1")
    resp = await client.get("/")
    assert resp.status == HTTPStatus.NOT_FOUND

    # Check that both invalid IP entries were logged
    for ip in ("Eo128.199.160.243", "invalidip"):
        assert (
            "homeassistant.components.http.ban",
            logging.ERROR,
            f"Failed to load IP ban: invalid IP address {ip}",
        ) in caplog.record_tuples


async def test_no_ip_bans_file(
    hass: HomeAssistant, aiohttp_client: ClientSessionGenerator
) -> None:
    """Test no ip bans file."""
    app = web.Application()
    app[KEY_HASS] = hass
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


async def test_failure_loading_ip_bans_file(
    hass: HomeAssistant, aiohttp_client: ClientSessionGenerator
) -> None:
    """Test failure loading ip bans file."""
    app = web.Application()
    app[KEY_HASS] = hass
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


async def test_ip_ban_manager_never_started(
    hass: HomeAssistant,
    aiohttp_client: ClientSessionGenerator,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test we handle the ip ban manager not being started."""
    app = web.Application()
    app[KEY_HASS] = hass
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
    ("remote_addr", "bans", "status"),
    list(
        zip(
            BANNED_IPS_WITH_SUPERVISOR,
            [1, 1, 0],
            [HTTPStatus.FORBIDDEN, HTTPStatus.FORBIDDEN, HTTPStatus.UNAUTHORIZED],
            strict=False,
        )
    ),
)
@pytest.mark.usefixtures(
    "hassio_env",
    "resolution_info",
    "os_info",
    "store_info",
    "supervisor_info",
    "supervisor_root_info",
    "homeassistant_info",
    "host_info",
    "network_info",
    "addons_list",
    "addon_info",
    "homeassistant_stats",
    "supervisor_stats",
    "ingress_panels",
)
async def test_access_from_supervisor_ip(
    remote_addr,
    bans,
    status,
    hass: HomeAssistant,
    aiohttp_client: ClientSessionGenerator,
) -> None:
    """Test accessing to server from supervisor IP."""
    app = web.Application()
    app[KEY_HASS] = hass

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

    manager = app[KEY_BAN_MANAGER]

    assert await async_setup_component(hass, "hassio", {"hassio": {}})

    m_open = mock_open()

    with (
        patch.dict(os.environ, {"SUPERVISOR": SUPERVISOR_IP}),
        patch("homeassistant.components.http.ban.open", m_open, create=True),
    ):
        resp = await client.get("/")
        assert resp.status == HTTPStatus.UNAUTHORIZED
        assert len(manager.ip_bans_lookup) == bans
        assert m_open.call_count == bans

        # second request should be forbidden if banned
        resp = await client.get("/")
        assert resp.status == status
        assert len(manager.ip_bans_lookup) == bans


@pytest.mark.freeze_time("2026-11-26T12:00:00+00:00")
@pytest.mark.parametrize(
    ("ban_duration", "banned_at", "status"),
    [
        pytest.param(
            None, "2016-11-16T19:20:03+00:00", HTTPStatus.FORBIDDEN, id="never_expires"
        ),
        pytest.param(
            60, "2026-11-26T11:30:00+00:00", HTTPStatus.FORBIDDEN, id="active"
        ),
        pytest.param(
            60, "2026-11-26T11:00:00+00:00", HTTPStatus.NOT_FOUND, id="expired"
        ),
    ],
)
async def test_ban_duration(
    hass: HomeAssistant,
    aiohttp_client: ClientSessionGenerator,
    ban_duration: int | None,
    banned_at: str,
    status: HTTPStatus,
) -> None:
    """Test bans expire after the ban duration."""
    app = web.Application()
    app[KEY_HASS] = hass
    setup_bans(hass, app, 5, ban_duration)
    mock_real_ip(app)(BANNED_IPS[0])

    with patch(
        "homeassistant.components.http.ban.load_yaml_config_file",
        return_value={BANNED_IPS[0]: {"banned_at": banned_at}},
    ):
        client = await aiohttp_client(app)

    resp = await client.get("/")
    assert resp.status == status


async def _setup_ban_file_client(
    hass: HomeAssistant,
    aiohttp_client: ClientSessionGenerator,
    ban_file: Path,
) -> TestClient:
    """Set up a client always failing auth, with bans stored in ban_file."""
    app = web.Application()
    app[KEY_HASS] = hass

    async def unauth_handler(request: web.Request) -> NoReturn:
        """Return a mock web response."""
        raise HTTPUnauthorized

    app.router.add_get("/", unauth_handler)
    setup_bans(hass, app, 2, 60)
    app[KEY_BAN_MANAGER].path = str(ban_file)
    mock_real_ip(app)("200.201.202.204")
    # Undo prevent_io, these tests read a real ban file
    with patch(
        "homeassistant.components.http.ban.load_yaml_config_file",
        load_yaml_config_file,
    ):
        return await aiohttp_client(app)


@pytest.mark.freeze_time("2026-11-26T12:00:00+00:00")
async def test_expired_ban_resets_failed_attempts(
    hass: HomeAssistant,
    aiohttp_client: ClientSessionGenerator,
    freezer: FrozenDateTimeFactory,
    tmp_path: Path,
) -> None:
    """Test an expired ban gives a fresh set of attempts and keeps one entry."""
    ban_file = tmp_path / IP_BANS_FILE
    client = await _setup_ban_file_client(hass, aiohttp_client, ban_file)

    for _ in range(2):
        assert (await client.get("/")).status == HTTPStatus.UNAUTHORIZED
    assert (await client.get("/")).status == HTTPStatus.FORBIDDEN

    freezer.tick(timedelta(minutes=60))

    # One failure is not enough to get banned again
    for _ in range(2):
        assert (await client.get("/")).status == HTTPStatus.UNAUTHORIZED
    assert (await client.get("/")).status == HTTPStatus.FORBIDDEN

    assert ban_file.read_text() == (
        "\n200.201.202.204:\n  banned_at: '2026-11-26T13:00:00+00:00'\n"
    )


@pytest.mark.freeze_time("2026-11-26T12:00:00+00:00")
@pytest.mark.parametrize(
    ("content_after_load", "expected"),
    [
        pytest.param(
            None,
            """# Managed by hand
200.201.202.204:
  # Office
  banned_at: '2026-11-26T12:00:00+00:00'  # first ban

100.64.0.2:
  banned_at: '2026-11-26T10:00:00+00:00'
""",
            id="entry_updated_in_place",
        ),
        pytest.param(
            "# Emptied by hand\n",
            "# Emptied by hand\n\n200.201.202.204:\n"
            "  banned_at: '2026-11-26T12:00:00+00:00'\n",
            id="entry_gone_appended",
        ),
    ],
)
async def test_ban_after_expiry_updates_ban_file(
    hass: HomeAssistant,
    aiohttp_client: ClientSessionGenerator,
    tmp_path: Path,
    content_after_load: str | None,
    expected: str,
) -> None:
    """Test banning again after expiry only changes banned_at in the ban file."""
    ban_file = tmp_path / IP_BANS_FILE
    ban_file.write_text(
        """# Managed by hand
200.201.202.204:
  # Office
  banned_at: '2026-11-26T10:00:00+00:00'  # first ban

100.64.0.2:
  banned_at: '2026-11-26T10:00:00+00:00'
"""
    )
    client = await _setup_ban_file_client(hass, aiohttp_client, ban_file)
    if content_after_load is not None:
        ban_file.write_text(content_after_load)

    for _ in range(2):
        assert (await client.get("/")).status == HTTPStatus.UNAUTHORIZED
    assert (await client.get("/")).status == HTTPStatus.FORBIDDEN

    assert ban_file.read_text() == expected


async def test_ban_middleware_not_loaded_by_config(hass: HomeAssistant) -> None:
    """Test accessing to server from banned IP when feature is off."""
    with patch("homeassistant.components.http.server.setup_bans") as mock_setup:
        await async_setup_component(
            hass, DOMAIN, {"http": {http.CONF_IP_BAN_ENABLED: False}}
        )

    assert len(mock_setup.mock_calls) == 0


async def test_ban_middleware_loaded_by_default(hass: HomeAssistant) -> None:
    """Test accessing to server from banned IP when feature is off."""
    with patch("homeassistant.components.http.server.setup_bans") as mock_setup:
        await async_setup_component(hass, DOMAIN, {"http": {}})

    assert len(mock_setup.mock_calls) == 1


async def test_ip_bans_file_creation(
    hass: HomeAssistant,
    aiohttp_client: ClientSessionGenerator,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Testing if banned IP file created."""
    app = web.Application()
    app[KEY_HASS] = hass

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

    manager = app[KEY_BAN_MANAGER]
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

        notifications = async_get_persistent_notifications(hass)
        assert len(notifications) == 2
        assert (
            notifications["http-login"]["message"]
            == "Login attempt or request with invalid authentication"
            " from example.com (200.201.202.204)."
            " See the log for details."
        )

        assert (
            "Login attempt or request with invalid authentication"
            " from example.com (200.201.202.204)."
            " Requested URL: '/example'." in caplog.text
        )


async def test_failed_login_attempts_counter(
    hass: HomeAssistant, aiohttp_client: ClientSessionGenerator
) -> None:
    """Testing if failed login attempts counter increased."""
    app = web.Application()
    app[KEY_HASS] = hass

    async def auth_handler(request):
        """Return 200 status code."""
        return None, 200

    async def auth_true_handler(request):
        """Return 200 status code."""
        process_success_login(request)
        return None, 200

    app.router.add_get(
        "/auth_true",
        request_handler_factory(hass, Mock(requires_auth=True), auth_true_handler),
    )
    app.router.add_get(
        "/auth_false",
        request_handler_factory(hass, Mock(requires_auth=True), auth_handler),
    )
    app.router.add_get(
        "/", request_handler_factory(hass, Mock(requires_auth=False), auth_handler)
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
    assert app[KEY_FAILED_LOGIN_ATTEMPTS][remote_ip] == 0

    resp = await client.get("/auth_false")
    assert resp.status == HTTPStatus.UNAUTHORIZED
    assert app[KEY_FAILED_LOGIN_ATTEMPTS][remote_ip] == 1

    resp = await client.get("/auth_false")
    assert resp.status == HTTPStatus.UNAUTHORIZED
    assert app[KEY_FAILED_LOGIN_ATTEMPTS][remote_ip] == 2


@pytest.mark.parametrize(
    ("lookup_error", "lookup_delay", "reverse_dns_timeout"),
    [
        pytest.param(None, 10, 0, id="slow_lookup"),
        pytest.param(herror(1, "Unknown host"), 0, 1, id="herror"),
        pytest.param(
            gaierror(-3, "Temporary failure in name resolution"),
            0,
            1,
            id="gaierror",
        ),
        pytest.param(
            UnicodeEncodeError("idna", "fe80::1%..", 9, 10, "label empty"),
            0,
            1,
            id="unencodable_scope_id",
        ),
    ],
)
async def test_failed_login_reverse_dns_failure(
    hass: HomeAssistant,
    aiohttp_client: ClientSessionGenerator,
    caplog: pytest.LogCaptureFixture,
    lookup_error: Exception | None,
    lookup_delay: float,
    reverse_dns_timeout: float,
) -> None:
    """Test that a slow or failing reverse DNS lookup still records the failed login."""
    app = web.Application()
    app[KEY_HASS] = hass

    async def unauth_handler(request):
        """Return a mock web response."""
        raise HTTPUnauthorized

    app.router.add_get("/", unauth_handler)
    setup_bans(hass, app, 5)
    mock_real_ip(app)("200.201.202.204")
    client = await aiohttp_client(app)

    release_lookup = threading.Event()
    lookup = Mock(side_effect=lookup_error, return_value=("example.com", [], []))

    def fake_gethostbyaddr(ip: str) -> tuple[str, list[str], list[str]]:
        """Wait out the delay, then defer to the lookup mock."""
        release_lookup.wait(lookup_delay)
        return lookup(ip)

    # Patch with a plain function so the test hass runs it in the executor
    with (
        patch(
            "homeassistant.components.http.ban.gethostbyaddr",
            fake_gethostbyaddr,
        ),
        patch(
            "homeassistant.components.http.ban.REVERSE_DNS_TIMEOUT",
            reverse_dns_timeout,
        ),
    ):
        resp = await client.get("/")
    release_lookup.set()

    assert resp.status == HTTPStatus.UNAUTHORIZED
    assert app[KEY_FAILED_LOGIN_ATTEMPTS][ip_address("200.201.202.204")] == 1
    assert (
        "Login attempt or request with invalid authentication"
        " from 200.201.202.204 (200.201.202.204)." in caplog.text
    )
    notifications = async_get_persistent_notifications(hass)
    assert (
        notifications["http-login"]["message"]
        == "Login attempt or request with invalid authentication"
        " from 200.201.202.204 (200.201.202.204)."
        " See the log for details."
    )


async def test_failed_login_attempts_counter_reverse_dns_unicode_decode_error(
    hass: HomeAssistant, aiohttp_client: ClientSessionGenerator
) -> None:
    """Test a wrong login still gets a 401 if the reverse DNS lookup fails to decode."""
    app = web.Application()
    app[KEY_HASS] = hass

    async def unauth_handler(request: web.Request) -> NoReturn:
        """Return a mock web response."""
        raise HTTPUnauthorized

    app.router.add_get("/example", unauth_handler)
    setup_bans(hass, app, 5)
    remote_ip = ip_address("200.201.202.204")
    mock_real_ip(app)("200.201.202.204")

    with patch(
        "homeassistant.components.http.ban.gethostbyaddr",
        side_effect=UnicodeDecodeError("utf-8", b"\x8a", 0, 1, "invalid start byte"),
    ):
        client = await aiohttp_client(app)
        resp = await client.get("/example")

    assert resp.status == HTTPStatus.UNAUTHORIZED
    assert app[KEY_FAILED_LOGIN_ATTEMPTS][remote_ip] == 1


async def test_wrong_login_is_counted_before_the_reverse_dns_lookup(
    hass: HomeAssistant, aiohttp_client: ClientSessionGenerator
) -> None:
    """Test a wrong login is counted and banned before the slow host lookup."""
    app = web.Application()
    app[KEY_HASS] = hass

    async def unauth_handler(request: web.Request) -> NoReturn:
        """Return a mock web response."""
        raise HTTPUnauthorized

    app.router.add_get("/example", unauth_handler)
    setup_bans(hass, app, 1)
    remote_ip = ip_address("200.201.202.204")
    mock_real_ip(app)("200.201.202.204")
    manager = app[KEY_BAN_MANAGER]
    seen_during_lookup: list[tuple[int, bool]] = []

    def gethostbyaddr(ip_addr: str) -> tuple[str, list[str], list[str]]:
        seen_during_lookup.append(
            (
                app[KEY_FAILED_LOGIN_ATTEMPTS][remote_ip],
                remote_ip in manager.ip_bans_lookup,
            )
        )
        return ("example.com", [], [])

    with (
        patch("homeassistant.components.http.ban.gethostbyaddr", gethostbyaddr),
        patch("homeassistant.components.http.ban.open", mock_open(), create=True),
    ):
        client = await aiohttp_client(app)
        resp = await client.get("/example")

    assert resp.status == HTTPStatus.UNAUTHORIZED
    assert seen_during_lookup == [(1, True)]


async def test_ban_applies_when_the_ban_file_cannot_be_written(
    hass: HomeAssistant,
    aiohttp_client: ClientSessionGenerator,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test a failing ban file write still bans and reports the attempt."""
    app = web.Application()
    app[KEY_HASS] = hass

    async def unauth_handler(request: web.Request) -> NoReturn:
        """Return a mock web response."""
        raise HTTPUnauthorized

    app.router.add_get("/example", unauth_handler)
    setup_bans(hass, app, 1)
    remote_ip = ip_address("200.201.202.204")
    mock_real_ip(app)("200.201.202.204")

    with patch(
        "homeassistant.components.http.ban.open",
        side_effect=OSError("Read-only file system"),
        create=True,
    ):
        client = await aiohttp_client(app)
        resp = await client.get("/example")

    assert resp.status == HTTPStatus.UNAUTHORIZED
    assert remote_ip in app[KEY_BAN_MANAGER].ip_bans_lookup
    assert (
        "Unable to save the ban of 200.201.202.204: Read-only file system"
        in caplog.text
    )
    notifications = async_get_persistent_notifications(hass)
    assert "http-login" in notifications
    assert "ip-ban" in notifications


async def test_single_ban_file_entry(
    hass: HomeAssistant,
) -> None:
    """Test that only one item is added to ban file."""
    app = web.Application()
    app[KEY_HASS] = hass

    async def unauth_handler(request):
        """Return a mock web response."""
        raise HTTPUnauthorized

    app.router.add_get("/example", unauth_handler)
    setup_bans(hass, app, 2)
    mock_real_ip(app)("200.201.202.204")

    manager = app[KEY_BAN_MANAGER]
    m_open = mock_open()

    with patch("homeassistant.components.http.ban.open", m_open, create=True):
        remote_ip = ip_address("200.201.202.204")
        await manager.async_add_ban(remote_ip)
        await manager.async_add_ban(remote_ip)

    assert m_open.call_count == 1


async def test_unix_socket_skips_ban_check(
    hass: HomeAssistant, aiohttp_client: ClientSessionGenerator
) -> None:
    """Test that Unix socket requests bypass ban middleware."""
    app = web.Application()
    app[KEY_HASS] = hass
    setup_bans(hass, app, 5)
    set_real_ip = mock_real_ip(app)

    with patch(
        "homeassistant.components.http.ban.load_yaml_config_file",
        return_value={
            banned_ip: {"banned_at": "2016-11-16T19:20:03"} for banned_ip in BANNED_IPS
        },
    ):
        client = await aiohttp_client(app)

    # Verify the IP is actually banned for normal requests
    set_real_ip(BANNED_IPS[0])
    resp = await client.get("/")
    assert resp.status == HTTPStatus.FORBIDDEN

    # Unix socket requests should bypass ban checks
    with patch(
        "homeassistant.components.http.ban.is_supervisor_unix_socket_request",
        return_value=True,
    ):
        resp = await client.get("/")
    assert resp.status == HTTPStatus.NOT_FOUND
