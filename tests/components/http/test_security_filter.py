"""Test security filter middleware."""

import asyncio
from collections.abc import Generator
from http import HTTPStatus
from pathlib import Path
from tempfile import TemporaryDirectory
import time
from unittest.mock import AsyncMock, Mock, patch

from aiohttp import ClientSession, UnixConnector, web
from aiohttp.hdrs import X_FORWARDED_FOR, X_FORWARDED_HOST, X_FORWARDED_PROTO
from aiohttp.test_utils import make_mocked_request
import pytest
from pytest_socket import socket_allow_hosts
import urllib3

from homeassistant.components.http.security_filter import FILTERS, setup_security_filter
from homeassistant.components.http.server import MAX_LINE_SIZE
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component

from tests.test_util import mock_real_ip
from tests.typing import ClientSessionGenerator


@pytest.fixture
def unix_socket_path() -> Generator[str]:
    """Keep the Unix socket path below the platform's length limit."""
    with TemporaryDirectory() as directory:
        yield str(Path(directory) / "http.sock")


async def mock_handler(request):
    """Return OK."""
    return web.Response(text="OK")


def long_target(prefix: str, unit: str, suffix: str = "") -> str:
    """Build a request target that fills up the maximum request line size."""
    room = MAX_LINE_SIZE - len(prefix) - len(suffix)
    return prefix + unit * (room // len(unit)) + suffix


@pytest.mark.parametrize(
    ("request_path", "request_params"),
    [
        ("/", {}),
        ("/lovelace/dashboard", {}),
        ("/frontend_latest/chunk.4c9e2d8dc10f77b885b0.js", {}),
        ("/static/translations/en-f96a262a5a6eede29234dc45dc63abf2.json", {}),
        ("/", {"test": "123"}),
    ],
)
async def test_ok_requests(
    request_path, request_params, aiohttp_client: ClientSessionGenerator
) -> None:
    """Test request paths that should not be filtered."""
    app = web.Application()
    app.router.add_get("/{all:.*}", mock_handler)

    setup_security_filter(app)

    mock_api_client = await aiohttp_client(app)
    resp = await mock_api_client.get(request_path, params=request_params)

    assert resp.status == HTTPStatus.OK
    assert await resp.text() == "OK"


@pytest.mark.parametrize(
    ("request_path", "request_params", "fail_on_query_string"),
    [
        ("/proc/self/environ", {}, False),
        ("/", {"test": "/test/../../api"}, True),
        ("/", {"test": "test/../../api"}, True),
        ("/", {"test": "/test/%2E%2E%2f%2E%2E%2fapi"}, True),
        ("/", {"test": "test/%2E%2E%2f%2E%2E%2fapi"}, True),
        ("/", {"test": "test/%252E%252E/api"}, True),
        ("/", {"test": "test/%252E%252E%2fapi"}, True),
        (
            "/",
            {"test": "test/%2525252E%2525252E%2525252f%2525252E%2525252E%2525252fapi"},
            True,
        ),
        ("/test/.%252E/api", {}, False),
        ("/test/%252E%252E/api", {}, False),
        ("/test/%2E%2E%2f%2E%2E%2fapi", {}, False),
        ("/test/%2525252E%2525252E%2525252f%2525252E%2525252E/api", {}, False),
        ("/", {"sql": ";UNION SELECT (a, b"}, True),
        ("/", {"sql": "UNION%20SELECT%20%28a%2C%20b"}, True),
        ("/UNION%20SELECT%20%28a%2C%20b", {}, False),
        ("/", {"sql": "concat(..."}, True),
        ("/", {"xss": "<script >"}, True),
        ("/<script >", {"xss": ""}, False),
        ("/%3Cscript%3E", {}, False),
    ],
)
async def test_bad_requests(
    request_path: str,
    request_params: dict[str, str],
    fail_on_query_string: bool,
    aiohttp_client: ClientSessionGenerator,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test request paths that should be filtered."""
    app = web.Application()
    app.router.add_get("/{all:.*}", mock_handler)

    setup_security_filter(app)

    mock_api_client = await aiohttp_client(app)

    # Manual params handling
    if request_params:
        raw_params = "&".join(f"{val}={key}" for val, key in request_params.items())
        man_params = f"?{raw_params}"
    else:
        man_params = ""

    http = urllib3.PoolManager()
    resp = await asyncio.get_running_loop().run_in_executor(
        None,
        http.request,
        "GET",
        f"http://{mock_api_client.host}:{mock_api_client.port}{request_path}{man_params}",
        request_params,
    )

    assert resp.status == HTTPStatus.BAD_REQUEST

    message = "Filtered a potential harmful request from 127.0.0.1:"
    if fail_on_query_string:
        message = (
            "Filtered a request with a potential harmful query string from 127.0.0.1:"
        )
    assert message in caplog.text


@pytest.mark.parametrize(
    ("request_path", "request_params", "fail_on_query_string"),
    [
        ("/some\thing", {}, False),
        ("/new\nline/cinema", {}, False),
        ("/return\r/to/sender", {}, False),
        ("/", {"some": "\thing"}, True),
        ("/", {"\newline": "cinema"}, True),
        ("/", {"return": "t\rue"}, True),
    ],
)
async def test_bad_requests_with_unsafe_bytes(
    request_path: str,
    request_params: dict[str, str],
    fail_on_query_string: bool,
    aiohttp_client: ClientSessionGenerator,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test request with unsafe bytes in their URLs."""
    app = web.Application()
    app.router.add_get("/{all:.*}", mock_handler)

    setup_security_filter(app)

    mock_api_client = await aiohttp_client(app)

    # Manual params handling
    if request_params:
        raw_params = "&".join(f"{val}={key}" for val, key in request_params.items())
        man_params = f"?{raw_params}"
    else:
        man_params = ""

    http = urllib3.PoolManager()
    resp = await asyncio.get_running_loop().run_in_executor(
        None,
        http.request,
        "GET",
        f"http://{mock_api_client.host}:{mock_api_client.port}{request_path}{man_params}",
        request_params,
    )

    assert resp.status == HTTPStatus.BAD_REQUEST

    message = "Filtered a request with an unsafe byte in path from 127.0.0.1:"
    if fail_on_query_string:
        message = "Filtered a request with unsafe byte query string from 127.0.0.1:"
    assert message in caplog.text


@pytest.mark.parametrize(
    "request_target",
    [
        pytest.param(long_target("/?a=<", "script"), id="unclosed_script_tag"),
        pytest.param(
            long_target("/?a=" + "<" * 64, "script"), id="many_opening_brackets"
        ),
        pytest.param(
            long_target("/?a=" + "%3C" * 64, "script"), id="many_encoded_brackets"
        ),
        pytest.param(
            long_target("/?a=" + "union" * 8, "all"), id="union_without_select"
        ),
        pytest.param(long_target("/?a=union", "select"), id="union_without_paren"),
        pytest.param(long_target("/?a=", "concat"), id="concat_without_paren"),
        pytest.param(long_target("/?a=", "<s\n"), id="short_lines"),
        pytest.param(
            long_target("/frontend_latest/", "chunk4c9e2d8/"), id="benign_path"
        ),
    ],
)
def test_long_unfiltered_targets_stay_cheap(request_target: str) -> None:
    """Test that a long request target that does not match stays cheap to filter.

    The bound is loose on purpose: it should fail when a branch starts
    backtracking again, not measure the machine it runs on. It goes at the
    pattern directly because the test server caps the request line well below
    MAX_LINE_SIZE, which also means the %3C cases arrive still encoded.
    """
    start = time.perf_counter()
    match = FILTERS.search(request_target)
    duration = time.perf_counter() - start

    assert match is None
    assert duration < 1


@pytest.mark.parametrize(
    "request_target",
    [
        pytest.param(long_target("/?a=<", "script", ">"), id="closed_script_tag"),
        pytest.param(long_target("/?a=%3C", "script", "%3E"), id="encoded_script_tag"),
        pytest.param(long_target("/?a=union", "all", "select"), id="union_all_select"),
        pytest.param(long_target("/?a=", "concat", "("), id="concat_paren"),
    ],
)
def test_long_filtered_targets_still_match(request_target: str) -> None:
    """Test that a long request target that should be filtered still matches."""
    assert FILTERS.search(request_target) is not None


@pytest.mark.parametrize(
    "request_path",
    [
        "/%3Cscript%3Ealert%3C/script%3E",
        "/%253Cscript%253E",
        "/%25253Cscript%25253E",
        "/%2525253Cscript%2525253E",
    ],
)
async def test_multiple_encoded_script_tags(
    request_path: str,
    aiohttp_client: ClientSessionGenerator,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test that repeatedly encoded script tags are unquoted and then filtered."""
    app = web.Application()
    app.router.add_get("/{all:.*}", mock_handler)

    setup_security_filter(app)

    mock_api_client = await aiohttp_client(app)

    http = urllib3.PoolManager()
    resp = await asyncio.get_running_loop().run_in_executor(
        None,
        http.request,
        "GET",
        f"http://{mock_api_client.host}:{mock_api_client.port}{request_path}",
    )

    assert resp.status == HTTPStatus.BAD_REQUEST
    assert "Filtered a potential harmful request from 127.0.0.1:" in caplog.text


@pytest.mark.parametrize(
    ("request_target", "message"),
    [
        ("/proc/self/environ", "Filtered a potential harmful request"),
        (
            "/?file=/proc/self/environ",
            "Filtered a request with a potential harmful query string",
        ),
        ("/new%0Aline", "Filtered a request with an unsafe byte in path"),
        ("/?value=new%0Aline", "Filtered a request with unsafe byte query string"),
    ],
)
@pytest.mark.parametrize(
    ("headers", "source"),
    [
        pytest.param([], "127.0.0.1", id="direct"),
        pytest.param([(X_FORWARDED_FOR, "198.51.100.1")], "198.51.100.1", id="proxy"),
        pytest.param(
            [(X_FORWARDED_FOR, "192.0.2.1, 198.51.100.1, 127.0.0.2")],
            "198.51.100.1",
            id="spoofed-prefix",
        ),
        pytest.param(
            [
                (X_FORWARDED_FOR, "192.0.2.1, 198.51.100.1"),
                (X_FORWARDED_FOR, "127.0.0.2"),
            ],
            "198.51.100.1",
            id="multiple-headers",
        ),
        pytest.param([(X_FORWARDED_FOR, "2001:db8::1")], "2001:db8::1", id="ipv6"),
    ],
)
async def test_filtered_request_source(
    hass: HomeAssistant,
    hass_client_no_auth: ClientSessionGenerator,
    caplog: pytest.LogCaptureFixture,
    request_target: str,
    message: str,
    headers: list[tuple[str, str]],
    source: str,
) -> None:
    """Resolve trusted forwarding headers before logging a blocked request."""
    assert await async_setup_component(
        hass,
        "http",
        {"http": {"use_x_forwarded_for": True, "trusted_proxies": ["127.0.0.0/24"]}},
    )
    handler = AsyncMock(return_value=web.Response())
    hass.http.app.router.add_get("/{all:.*}", handler)
    client = await hass_client_no_auth()

    response = await client.get(request_target, headers=headers)

    assert response.status == HTTPStatus.BAD_REQUEST
    assert f"{message} from {source}: {request_target}" in caplog.text
    handler.assert_not_awaited()


@pytest.mark.parametrize(
    ("use_x_forwarded_for", "trusted_proxies", "headers", "message"),
    [
        (True, [], [(X_FORWARDED_FOR, "198.51.100.1")], "untrusted proxy 127.0.0.1"),
        (
            False,
            [],
            [(X_FORWARDED_FOR, "198.51.100.1")],
            "not set-up for reverse proxies",
        ),
        (
            True,
            ["127.0.0.1"],
            [(X_FORWARDED_FOR, "invalid")],
            "Invalid IP address in X-Forwarded-For",
        ),
        (
            True,
            ["127.0.0.1"],
            [(X_FORWARDED_FOR, "198.51.100.1"), (X_FORWARDED_PROTO, "")],
            "Empty item received in X-Forward-Proto",
        ),
        (
            True,
            ["127.0.0.1"],
            [(X_FORWARDED_FOR, "198.51.100.1"), (X_FORWARDED_HOST, "")],
            "Empty value received in X-Forward-Host",
        ),
    ],
)
async def test_filtered_request_rejects_invalid_forwarding(
    hass: HomeAssistant,
    hass_client_no_auth: ClientSessionGenerator,
    caplog: pytest.LogCaptureFixture,
    use_x_forwarded_for: bool,
    trusted_proxies: list[str],
    headers: list[tuple[str, str]],
    message: str,
) -> None:
    """Reject invalid forwarding without attributing a request to its claimed source."""
    assert await async_setup_component(
        hass,
        "http",
        {
            "http": {
                "use_x_forwarded_for": use_x_forwarded_for,
                "trusted_proxies": trusted_proxies,
            }
        },
    )
    client = await hass_client_no_auth()

    response = await client.get("/proc/self/environ", headers=headers)

    assert response.status == HTTPStatus.BAD_REQUEST
    assert message in caplog.text
    assert "Filtered a" not in caplog.text


async def test_filtered_cloud_request_source(
    hass: HomeAssistant,
    hass_client_no_auth: ClientSessionGenerator,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Cloud requests keep the tunnel's peer address and ignore forwarding headers."""
    assert await async_setup_component(
        hass,
        "http",
        {"http": {"use_x_forwarded_for": True, "trusted_proxies": ["127.0.0.1"]}},
    )
    mock_real_ip(hass.http.app)("198.51.100.1")
    client = await hass_client_no_auth()

    with patch(
        "hass_nabucasa.remote.is_cloud_request", Mock(get=Mock(return_value=True))
    ):
        response = await client.get(
            "/proc/self/environ",
            headers={X_FORWARDED_FOR: "192.0.2.1", X_FORWARDED_HOST: ""},
        )

    assert response.status == HTTPStatus.BAD_REQUEST
    assert (
        "Filtered a potential harmful request from 198.51.100.1: /proc/self/environ"
        in caplog.text
    )
    assert "192.0.2.1" not in caplog.text


@pytest.mark.usefixtures("socket_enabled")
async def test_filtered_unix_socket_request_with_forwarding_headers(
    hass: HomeAssistant,
    caplog: pytest.LogCaptureFixture,
    unix_socket_path: str,
) -> None:
    """Unix socket requests ignore claimed IPs and still reach the security filter."""
    socket_allow_hosts(["127.0.0.1"], allow_unix_socket=True)
    assert await async_setup_component(
        hass,
        "http",
        {"http": {"use_x_forwarded_for": True, "trusted_proxies": ["127.0.0.1"]}},
    )
    runner = web.AppRunner(hass.http.app)
    await runner.setup()
    try:
        await web.UnixSite(runner, unix_socket_path).start()
        async with ClientSession(
            connector=UnixConnector(path=unix_socket_path)
        ) as client:
            response = await client.get(
                "http://localhost/proc/self/environ",
                headers={X_FORWARDED_FOR: "198.51.100.1"},
            )
            assert response.status == HTTPStatus.BAD_REQUEST
    finally:
        await runner.cleanup()

    assert (
        "Filtered a potential harmful request from unknown: /proc/self/environ"
        in caplog.text
    )
    assert "198.51.100.1" not in caplog.text


@pytest.mark.parametrize("peername", [None, "", "/run/supervisor.sock"])
async def test_filtered_request_without_ip_peer(
    caplog: pytest.LogCaptureFixture, peername: str | None
) -> None:
    """Missing and Unix socket peers still produce a filtered response."""
    app = web.Application()
    setup_security_filter(app)
    request = make_mocked_request(
        "GET",
        "/proc/self/environ",
        transport=Mock(get_extra_info=Mock(return_value=peername)),
    )
    handler = AsyncMock()

    with pytest.raises(web.HTTPBadRequest):
        await app.middlewares[0](request, handler)

    assert (
        f"Filtered a potential harmful request from {peername or 'unknown'}: /proc/self/environ"
        in caplog.text
    )
    handler.assert_not_awaited()
