"""The tests for the Home Assistant HTTP component."""

from collections import defaultdict
from http import HTTPStatus
from ipaddress import ip_address
import os
from pathlib import Path
from socket import gaierror, herror
import threading
from typing import Any, NoReturn
from unittest.mock import AsyncMock, Mock, patch

from aiohttp import web
from aiohttp.web_exceptions import HTTPUnauthorized
from aiohttp.web_middlewares import middleware
from freezegun.api import FrozenDateTimeFactory
import probatio
import pytest
from pytest_homeassistant.common import MockUser, async_get_persistent_notifications
from pytest_homeassistant.typing import ClientSessionGenerator, WebSocketGenerator

from homeassistant.components import http
from homeassistant.components.http import DOMAIN
from homeassistant.components.http.ban import (
    KEY_BAN_MANAGER,
    KEY_FAILED_LOGIN_ATTEMPTS,
    STORAGE_KEY,
    IpBanManager,
    ban_middleware,
    process_success_login,
    process_wrong_login,
    setup_bans,
)
from homeassistant.components.http.view import request_handler_factory
from homeassistant.core import Context, HomeAssistant
from homeassistant.exceptions import ServiceValidationError, Unauthorized
from homeassistant.helpers import issue_registry as ir
from homeassistant.helpers.http import KEY_AUTHENTICATED, KEY_HASS
from homeassistant.helpers.storage import Store
from homeassistant.setup import async_setup_component
from homeassistant.util.file import WriteError

from tests.test_util import mock_real_ip

SUPERVISOR_IP = "1.2.3.4"
BANNED_IPS = ["200.201.202.203", "100.64.0.2"]
BANNED_IPS_WITH_SUPERVISOR = [*BANNED_IPS, SUPERVISOR_IP]


def stored_bans(
    bans: dict[str, str], yaml_migration_done: bool = True
) -> dict[str, Any]:
    """Return the IP ban store holding the given bans."""
    return {
        "version": 1,
        "minor_version": 1,
        "key": STORAGE_KEY,
        "data": {
            "ip_bans": [
                {"ip_address": ip, "banned_at": banned_at}
                for ip, banned_at in bans.items()
            ],
            "yaml_migration_done": yaml_migration_done,
        },
    }


@pytest.fixture
def banned_ips(hass_storage: dict[str, Any]) -> None:
    """Store bans of BANNED_IPS."""
    hass_storage[STORAGE_KEY] = stored_bans(
        dict.fromkeys(BANNED_IPS, "2016-11-16T19:20:03+00:00")
    )


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


@pytest.mark.usefixtures("banned_ips")
async def test_access_from_banned_ip(
    hass: HomeAssistant, aiohttp_client: ClientSessionGenerator
) -> None:
    """Test accessing to server from banned IP. Both trusted and not."""
    app = web.Application()
    app[KEY_HASS] = hass
    setup_bans(hass, app, 5)
    set_real_ip = mock_real_ip(app)

    client = await aiohttp_client(app)

    for remote_addr in BANNED_IPS:
        set_real_ip(remote_addr)
        resp = await client.get("/")
        assert resp.status == HTTPStatus.FORBIDDEN


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
    remote_addr: str,
    bans: int,
    status: HTTPStatus,
    hass: HomeAssistant,
    hass_storage: dict[str, Any],
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
    client = await aiohttp_client(app)

    manager = app[KEY_BAN_MANAGER]

    assert await async_setup_component(hass, "hassio", {"hassio": {}})

    with patch.dict(os.environ, {"SUPERVISOR": SUPERVISOR_IP}):
        resp = await client.get("/")
        assert resp.status == HTTPStatus.UNAUTHORIZED
        assert len(manager.ip_bans_lookup) == bans
        assert len(hass_storage[STORAGE_KEY]["data"]["ip_bans"]) == bans

        # second request should be forbidden if banned
        resp = await client.get("/")
        assert resp.status == status
        assert len(manager.ip_bans_lookup) == bans


@pytest.mark.parametrize(
    ("config", "middleware_loaded"),
    [
        pytest.param({}, True, id="default"),
        pytest.param({http.CONF_IP_BAN_ENABLED: False}, False, id="disabled"),
    ],
)
async def test_ban_middleware_loaded_by_config(
    hass: HomeAssistant, config: dict[str, Any], middleware_loaded: bool
) -> None:
    """Test the middleware follows the config and the manager is always set up."""
    assert await async_setup_component(hass, DOMAIN, {DOMAIN: config})

    assert (ban_middleware in hass.http.app.middlewares) is middleware_loaded
    assert KEY_BAN_MANAGER in hass.http.app


async def test_wrong_login_does_not_ban_when_disabled(
    hass: HomeAssistant, aiohttp_client: ClientSessionGenerator
) -> None:
    """Test failed logins are not counted or banned with banning disabled."""
    app = web.Application()
    app[KEY_HASS] = hass

    async def unauth_handler(request: web.Request) -> NoReturn:
        """Report a wrong login like the login flow does."""
        await process_wrong_login(request)
        raise HTTPUnauthorized

    app.router.add_get("/example", unauth_handler)
    setup_bans(hass, app, 1, is_ban_enabled=False)
    mock_real_ip(app)("200.201.202.204")
    client = await aiohttp_client(app)

    resp = await client.get("/example")

    assert resp.status == HTTPStatus.UNAUTHORIZED
    assert not app[KEY_BAN_MANAGER].ip_bans_lookup
    assert not app[KEY_FAILED_LOGIN_ATTEMPTS]


@pytest.mark.usefixtures("banned_ips")
async def test_ip_ban_stored(
    hass: HomeAssistant,
    hass_storage: dict[str, Any],
    aiohttp_client: ClientSessionGenerator,
    caplog: pytest.LogCaptureFixture,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test a new ban is stored and announced."""
    freezer.move_to("2026-11-27T10:15:00+00:00")
    app = web.Application()
    app[KEY_HASS] = hass

    async def unauth_handler(request):
        """Return a mock web response."""
        raise HTTPUnauthorized

    app.router.add_get("/example", unauth_handler)
    setup_bans(hass, app, 2)
    mock_real_ip(app)("200.201.202.204")
    client = await aiohttp_client(app)

    manager = app[KEY_BAN_MANAGER]

    resp = await client.get("/example")
    assert resp.status == HTTPStatus.UNAUTHORIZED
    assert len(manager.ip_bans_lookup) == len(BANNED_IPS)

    resp = await client.get("/example")
    assert resp.status == HTTPStatus.UNAUTHORIZED
    assert len(manager.ip_bans_lookup) == len(BANNED_IPS) + 1
    assert hass_storage[STORAGE_KEY] == stored_bans(
        {
            **dict.fromkeys(BANNED_IPS, "2016-11-16T19:20:03+00:00"),
            "200.201.202.204": "2026-11-27T10:15:00+00:00",
        }
    )

    resp = await client.get("/example")
    assert resp.status == HTTPStatus.FORBIDDEN

    notifications = async_get_persistent_notifications(hass)
    assert len(notifications) == 2
    assert (
        notifications["http-login"]["message"]
        == "Login attempt or request with invalid authentication"
        " from example.com (200.201.202.204)."
        " See the log for details."
    )
    assert notifications["ip-ban"]["message"] == (
        "Too many login attempts from 200.201.202.204. You can unblock it under"
        " [Settings > System > Network](/config/network)."
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

    with patch("homeassistant.components.http.ban.gethostbyaddr", gethostbyaddr):
        client = await aiohttp_client(app)
        resp = await client.get("/example")

    assert resp.status == HTTPStatus.UNAUTHORIZED
    assert seen_during_lookup == [(1, True)]


async def test_ban_applies_when_the_store_cannot_be_written(
    hass: HomeAssistant,
    aiohttp_client: ClientSessionGenerator,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test a failing store write still bans and reports the attempt."""
    app = web.Application()
    app[KEY_HASS] = hass

    async def unauth_handler(request: web.Request) -> NoReturn:
        """Return a mock web response."""
        raise HTTPUnauthorized

    app.router.add_get("/example", unauth_handler)
    setup_bans(hass, app, 1)
    remote_ip = ip_address("200.201.202.204")
    mock_real_ip(app)("200.201.202.204")

    with patch.object(
        Store,
        "_async_write_data",
        side_effect=WriteError("Read-only file system"),
    ):
        client = await aiohttp_client(app)
        resp = await client.get("/example")

    assert resp.status == HTTPStatus.UNAUTHORIZED
    assert remote_ip in app[KEY_BAN_MANAGER].ip_bans_lookup
    assert (
        f"Error writing config for {STORAGE_KEY}: Read-only file system" in caplog.text
    )
    notifications = async_get_persistent_notifications(hass)
    assert "http-login" in notifications
    assert "ip-ban" in notifications


async def test_single_ban_entry(
    hass: HomeAssistant,
) -> None:
    """Test that banning an address twice stores it once."""
    app = web.Application()
    app[KEY_HASS] = hass

    async def unauth_handler(request):
        """Return a mock web response."""
        raise HTTPUnauthorized

    app.router.add_get("/example", unauth_handler)
    setup_bans(hass, app, 2)
    mock_real_ip(app)("200.201.202.204")

    manager = app[KEY_BAN_MANAGER]

    with patch.object(Store, "async_save") as mock_save:
        remote_ip = ip_address("200.201.202.204")
        await manager.async_add_ban(remote_ip)
        await manager.async_add_ban(remote_ip)

    assert mock_save.call_count == 1


@pytest.mark.usefixtures("banned_ips")
async def test_unix_socket_skips_ban_check(
    hass: HomeAssistant, aiohttp_client: ClientSessionGenerator
) -> None:
    """Test that Unix socket requests bypass ban middleware."""
    app = web.Application()
    app[KEY_HASS] = hass
    setup_bans(hass, app, 5)
    set_real_ip = mock_real_ip(app)
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


async def load_ip_bans(hass: HomeAssistant) -> IpBanManager:
    """Load the IP bans like the server does on startup."""
    manager = IpBanManager(hass, defaultdict(int))
    await manager.async_load()
    return manager


@pytest.fixture
def config_dir(hass: HomeAssistant, tmp_path: Path) -> Path:
    """Use a temporary configuration directory."""
    hass.config.config_dir = str(tmp_path)
    return tmp_path


@pytest.mark.parametrize(
    ("content", "expected"),
    [
        pytest.param(
            "200.201.202.203:\n"
            "  banned_at: '2016-11-16T19:20:03+00:00'\n"
            "100.64.0.2:\n"
            "  banned_at: '2016-11-16T19:20:03'\n",
            {
                "200.201.202.203": "2016-11-16T19:20:03+00:00",
                "100.64.0.2": "2016-11-16T19:20:03+00:00",
            },
            id="valid",
        ),
        pytest.param(
            "5.3.3.3:\n"
            "  banned_at: garbage\n"
            "5.3.3.4: {}\n"
            "5.3.3.5:\n"
            "Eo128.199.160.243:\n"
            "  banned_at: '2024-07-06T14:07:46'\n",
            {
                "5.3.3.4": "2026-11-27T10:15:00+00:00",
                "5.3.3.5": "2026-11-27T10:15:00+00:00",
            },
            id="malformed_entries_skipped",
        ),
        pytest.param("", {}, id="empty_file"),
    ],
)
async def test_yaml_import(
    hass: HomeAssistant,
    hass_storage: dict[str, Any],
    issue_registry: ir.IssueRegistry,
    config_dir: Path,
    caplog: pytest.LogCaptureFixture,
    freezer: FrozenDateTimeFactory,
    content: str,
    expected: dict[str, str],
) -> None:
    """Test ip_bans.yaml is imported once and renamed."""
    freezer.move_to("2026-11-27T10:15:00+00:00")
    (config_dir / "ip_bans.yaml").write_text(content)

    manager = await load_ip_bans(hass)

    assert {str(ip) for ip in manager.ip_bans_lookup} == set(expected)
    assert hass_storage[STORAGE_KEY] == stored_bans(expected)
    assert not (config_dir / "ip_bans.yaml").exists()
    assert (config_dir / "ip_bans.yaml.migrated").read_text() == content
    assert "Imported the IP bans from" in caplog.text
    assert not issue_registry.issues


async def test_yaml_import_logs_malformed_entries(
    hass: HomeAssistant, config_dir: Path, caplog: pytest.LogCaptureFixture
) -> None:
    """Test malformed entries of ip_bans.yaml are logged."""
    (config_dir / "ip_bans.yaml").write_text(
        "5.3.3.3:\n  banned_at: garbage\nEo128.199.160.243: {}\n"
    )

    await load_ip_bans(hass)

    assert "Failed to load IP ban {'banned_at': 'garbage'}" in caplog.text
    assert "Failed to load IP ban: invalid IP address Eo128.199.160.243" in caplog.text


async def test_no_yaml_file(
    hass: HomeAssistant, hass_storage: dict[str, Any], config_dir: Path
) -> None:
    """Test a new installation marks the import as done."""
    manager = await load_ip_bans(hass)

    assert not manager.ip_bans_lookup
    assert hass_storage[STORAGE_KEY] == stored_bans({})
    assert not (config_dir / "ip_bans.yaml.migrated").exists()


@pytest.mark.parametrize(
    "content",
    [
        pytest.param("200.201.202.203: [\n", id="invalid_yaml"),
        pytest.param("- 200.201.202.203\n", id="not_a_dict"),
    ],
)
async def test_yaml_import_error(
    hass: HomeAssistant,
    hass_storage: dict[str, Any],
    issue_registry: ir.IssueRegistry,
    config_dir: Path,
    content: str,
) -> None:
    """Test an unreadable ip_bans.yaml raises a repair and is left alone."""
    (config_dir / "ip_bans.yaml").write_text(content)

    manager = await load_ip_bans(hass)

    assert not manager.ip_bans_lookup
    assert STORAGE_KEY not in hass_storage
    assert (config_dir / "ip_bans.yaml").read_text() == content
    issue = issue_registry.async_get_issue(DOMAIN, "ip_bans_yaml_import_error")
    assert issue is not None
    assert issue.severity is ir.IssueSeverity.ERROR


async def test_yaml_import_after_fix_keeps_stored_bans(
    hass: HomeAssistant, hass_storage: dict[str, Any], config_dir: Path
) -> None:
    """Test a corrected ip_bans.yaml is merged into bans stored meanwhile."""
    hass_storage[STORAGE_KEY] = stored_bans(
        {BANNED_IPS[0]: "2026-11-20T08:00:00+00:00"}, yaml_migration_done=False
    )
    (config_dir / "ip_bans.yaml").write_text(
        f"{BANNED_IPS[0]}:\n"
        "  banned_at: '2016-11-16T19:20:03+00:00'\n"
        f"{BANNED_IPS[1]}:\n"
        "  banned_at: '2016-11-16T19:20:03+00:00'\n"
    )

    await load_ip_bans(hass)

    assert hass_storage[STORAGE_KEY] == stored_bans(
        {
            BANNED_IPS[0]: "2026-11-20T08:00:00+00:00",
            BANNED_IPS[1]: "2016-11-16T19:20:03+00:00",
        }
    )
    assert (config_dir / "ip_bans.yaml.migrated").exists()


async def test_yaml_ignored_after_migration(
    hass: HomeAssistant,
    hass_storage: dict[str, Any],
    issue_registry: ir.IssueRegistry,
    config_dir: Path,
) -> None:
    """Test an ip_bans.yaml showing up after the import raises a repair."""
    hass_storage[STORAGE_KEY] = stored_bans(
        {BANNED_IPS[0]: "2016-11-16T19:20:03+00:00"}
    )
    (config_dir / "ip_bans.yaml").write_text(f"{BANNED_IPS[1]}: {{}}\n")

    manager = await load_ip_bans(hass)

    assert set(manager.ip_bans_lookup) == {ip_address(BANNED_IPS[0])}
    assert (config_dir / "ip_bans.yaml").exists()
    assert not (config_dir / "ip_bans.yaml.migrated").exists()
    issue = issue_registry.async_get_issue(DOMAIN, "ip_bans_yaml_ignored")
    assert issue is not None
    assert issue.severity is ir.IssueSeverity.WARNING


async def test_yaml_kept_when_store_cannot_be_written(
    hass: HomeAssistant, config_dir: Path, caplog: pytest.LogCaptureFixture
) -> None:
    """Test ip_bans.yaml stays and its bans apply when the store can't be written."""
    (config_dir / "ip_bans.yaml").write_text(f"{BANNED_IPS[0]}: {{}}\n")

    with patch.object(
        Store, "_async_write_data", side_effect=WriteError("Read-only file system")
    ):
        manager = await load_ip_bans(hass)

    assert set(manager.ip_bans_lookup) == {ip_address(BANNED_IPS[0])}
    assert (config_dir / "ip_bans.yaml").exists()
    assert "Unable to store the IP bans imported from" in caplog.text


async def test_yaml_rename_fails(
    hass: HomeAssistant,
    hass_storage: dict[str, Any],
    config_dir: Path,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test a failing rename after the import is logged."""
    (config_dir / "ip_bans.yaml").write_text(f"{BANNED_IPS[0]}: {{}}\n")

    with patch(
        "homeassistant.components.http.ban.os.replace",
        side_effect=OSError("Permission denied"),
    ):
        await load_ip_bans(hass)

    assert hass_storage[STORAGE_KEY]["data"]["yaml_migration_done"] is True
    assert (config_dir / "ip_bans.yaml").exists()
    assert "Unable to rename" in caplog.text


@pytest.mark.parametrize(
    "stored",
    [
        pytest.param(
            {"version": 2, "minor_version": 1, "key": STORAGE_KEY, "data": {}},
            id="newer_version",
        ),
        pytest.param(
            {"version": 1, "minor_version": 1, "key": STORAGE_KEY, "data": ["x"]},
            id="wrong_shape",
        ),
    ],
)
@pytest.mark.usefixtures("config_dir")
async def test_unreadable_store_means_no_bans(
    hass: HomeAssistant,
    hass_storage: dict[str, Any],
    caplog: pytest.LogCaptureFixture,
    stored: dict[str, Any],
) -> None:
    """Test an unreadable store loads without bans instead of failing."""
    hass_storage[STORAGE_KEY] = stored

    manager = await load_ip_bans(hass)

    assert not manager.ip_bans_lookup
    assert "Unable to load the IP bans" in caplog.text


@pytest.mark.usefixtures("config_dir")
async def test_invalid_stored_bans_skipped(
    hass: HomeAssistant,
    hass_storage: dict[str, Any],
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test invalid stored bans are skipped and the valid ones load."""
    hass_storage[STORAGE_KEY] = stored_bans(
        {
            BANNED_IPS[0]: "2016-11-16T19:20:03+00:00",
            "invalidip": "2016-11-16T19:20:03+00:00",
            BANNED_IPS[1]: "garbage",
        }
    )

    manager = await load_ip_bans(hass)

    assert set(manager.ip_bans_lookup) == {ip_address(BANNED_IPS[0])}
    assert caplog.text.count("Failed to load IP ban") == 2


@pytest.mark.usefixtures("banned_ips", "config_dir")
async def test_bans_persist_across_restart(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory
) -> None:
    """Test added and removed bans are kept after a restart."""
    freezer.move_to("2026-11-27T10:15:00+00:00")
    manager = await load_ip_bans(hass)
    await manager.async_add_ban(ip_address("203.0.113.7"))
    assert await manager.async_remove_ban(ip_address(BANNED_IPS[0]))

    restarted = await load_ip_bans(hass)

    assert {
        str(ip): ban.banned_at.isoformat()
        for ip, ban in restarted.ip_bans_lookup.items()
    } == {
        BANNED_IPS[1]: "2016-11-16T19:20:03+00:00",
        "203.0.113.7": "2026-11-27T10:15:00+00:00",
    }


@pytest.mark.usefixtures("banned_ips")
async def test_remove_ban_applies_immediately(
    hass: HomeAssistant,
    hass_storage: dict[str, Any],
    aiohttp_client: ClientSessionGenerator,
) -> None:
    """Test removing a ban lifts it right away and resets the counter."""
    app = web.Application()
    app[KEY_HASS] = hass
    setup_bans(hass, app, 5)
    mock_real_ip(app)(BANNED_IPS[0])
    client = await aiohttp_client(app)
    remote_ip = ip_address(BANNED_IPS[0])
    app[KEY_FAILED_LOGIN_ATTEMPTS][remote_ip] = 5

    resp = await client.get("/")
    assert resp.status == HTTPStatus.FORBIDDEN

    assert await app[KEY_BAN_MANAGER].async_remove_ban(remote_ip)

    resp = await client.get("/")
    assert resp.status == HTTPStatus.NOT_FOUND
    assert remote_ip not in app[KEY_FAILED_LOGIN_ATTEMPTS]
    assert hass_storage[STORAGE_KEY] == stored_bans(
        {BANNED_IPS[1]: "2016-11-16T19:20:03+00:00"}
    )
    assert not await app[KEY_BAN_MANAGER].async_remove_ban(remote_ip)


async def test_websocket_list_ip_bans(
    hass: HomeAssistant,
    hass_storage: dict[str, Any],
    hass_ws_client: WebSocketGenerator,
) -> None:
    """Test listing the IP bans, newest first."""
    hass_storage[STORAGE_KEY] = stored_bans(
        {
            "100.64.0.2": "2016-11-16T19:20:03",
            "203.0.113.7": "2026-11-27T10:15:00+00:00",
            "2001:db8::1": "2026-11-20T08:00:00+01:00",
        }
    )
    assert await async_setup_component(hass, DOMAIN, {})
    assert await async_setup_component(hass, "websocket_api", {})
    ws_client = await hass_ws_client(hass)

    await ws_client.send_json_auto_id({"type": "http/ip_bans/list"})
    response = await ws_client.receive_json()

    assert response["success"]
    assert response["result"] == {
        "ip_bans": [
            {"ip_address": "203.0.113.7", "banned_at": "2026-11-27T10:15:00+00:00"},
            {"ip_address": "2001:db8::1", "banned_at": "2026-11-20T07:00:00+00:00"},
            {"ip_address": "100.64.0.2", "banned_at": "2016-11-16T19:20:03+00:00"},
        ]
    }


@pytest.mark.usefixtures("banned_ips")
async def test_websocket_remove_ip_ban(
    hass: HomeAssistant,
    hass_storage: dict[str, Any],
    hass_ws_client: WebSocketGenerator,
) -> None:
    """Test removing an IP ban."""
    assert await async_setup_component(hass, DOMAIN, {})
    assert await async_setup_component(hass, "websocket_api", {})
    ws_client = await hass_ws_client(hass)
    hass.http.app[KEY_FAILED_LOGIN_ATTEMPTS][ip_address(BANNED_IPS[0])] = 5

    await ws_client.send_json_auto_id(
        {"type": "http/ip_bans/remove", "ip_address": BANNED_IPS[0]}
    )
    response = await ws_client.receive_json()

    assert response["success"]
    assert response["result"] is None
    assert set(hass.http.app[KEY_BAN_MANAGER].ip_bans_lookup) == {
        ip_address(BANNED_IPS[1])
    }
    assert not hass.http.app[KEY_FAILED_LOGIN_ATTEMPTS]
    assert hass_storage[STORAGE_KEY] == stored_bans(
        {BANNED_IPS[1]: "2016-11-16T19:20:03+00:00"}
    )


@pytest.mark.parametrize(
    ("ip", "error_code"),
    [
        pytest.param("203.0.113.7", "not_found", id="not_banned"),
        pytest.param("203.0.113", "invalid_format", id="invalid_address"),
    ],
)
@pytest.mark.usefixtures("banned_ips")
async def test_websocket_remove_ip_ban_error(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    ip: str,
    error_code: str,
) -> None:
    """Test removing an address that is not banned or not an address."""
    assert await async_setup_component(hass, DOMAIN, {})
    assert await async_setup_component(hass, "websocket_api", {})
    ws_client = await hass_ws_client(hass)

    await ws_client.send_json_auto_id({"type": "http/ip_bans/remove", "ip_address": ip})
    response = await ws_client.receive_json()

    assert not response["success"]
    assert response["error"]["code"] == error_code
    assert len(hass.http.app[KEY_BAN_MANAGER].ip_bans_lookup) == len(BANNED_IPS)


@pytest.mark.parametrize(
    "message",
    [
        pytest.param({"type": "http/ip_bans/list"}, id="list"),
        pytest.param(
            {"type": "http/ip_bans/remove", "ip_address": BANNED_IPS[0]}, id="remove"
        ),
    ],
)
@pytest.mark.usefixtures("banned_ips")
async def test_websocket_ip_bans_require_admin(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    hass_read_only_access_token: str,
    message: dict[str, Any],
) -> None:
    """Test the IP ban commands are admin only."""
    assert await async_setup_component(hass, DOMAIN, {})
    assert await async_setup_component(hass, "websocket_api", {})
    ws_client = await hass_ws_client(hass, hass_read_only_access_token)

    await ws_client.send_json_auto_id(message)
    response = await ws_client.receive_json()

    assert not response["success"]
    assert response["error"]["code"] == "unauthorized"
    assert len(hass.http.app[KEY_BAN_MANAGER].ip_bans_lookup) == len(BANNED_IPS)


async def test_unban_action(hass: HomeAssistant, hass_storage: dict[str, Any]) -> None:
    """Test the unban action lifts a ban and resets the counter."""
    assert await async_setup_component(hass, DOMAIN, {})
    remote_ip = ip_address("203.0.113.7")
    await hass.http.app[KEY_BAN_MANAGER].async_add_ban(remote_ip)
    hass.http.app[KEY_FAILED_LOGIN_ATTEMPTS][remote_ip] = 5

    await hass.services.async_call(
        DOMAIN, "unban", {"ip_address": "203.0.113.7"}, blocking=True
    )

    assert not hass.http.app[KEY_BAN_MANAGER].ip_bans_lookup
    assert not hass.http.app[KEY_FAILED_LOGIN_ATTEMPTS]
    assert hass_storage[STORAGE_KEY]["data"]["ip_bans"] == []


async def test_unban_action_not_banned(hass: HomeAssistant) -> None:
    """Test the unban action rejects an address that is not banned."""
    assert await async_setup_component(hass, DOMAIN, {})

    with pytest.raises(ServiceValidationError) as exc_info:
        await hass.services.async_call(
            DOMAIN, "unban", {"ip_address": "203.0.113.7"}, blocking=True
        )

    assert exc_info.value.translation_key == "ip_address_not_banned"
    assert exc_info.value.translation_placeholders == {"ip_address": "203.0.113.7"}


async def test_unban_action_invalid_address(hass: HomeAssistant) -> None:
    """Test the unban action rejects an invalid address."""
    assert await async_setup_component(hass, DOMAIN, {})

    with pytest.raises(probatio.Invalid):
        await hass.services.async_call(
            DOMAIN, "unban", {"ip_address": "203.0.113"}, blocking=True
        )


async def test_unban_action_requires_admin(
    hass: HomeAssistant, hass_read_only_user: MockUser
) -> None:
    """Test the unban action is admin only."""
    assert await async_setup_component(hass, DOMAIN, {})
    remote_ip = ip_address("203.0.113.7")
    await hass.http.app[KEY_BAN_MANAGER].async_add_ban(remote_ip)

    with pytest.raises(Unauthorized):
        await hass.services.async_call(
            DOMAIN,
            "unban",
            {"ip_address": "203.0.113.7"},
            blocking=True,
            context=Context(user_id=hass_read_only_user.id),
        )

    assert remote_ip in hass.http.app[KEY_BAN_MANAGER].ip_bans_lookup
