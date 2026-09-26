"""Test security filter middleware."""

import asyncio
from http import HTTPStatus
import time

from aiohttp import web
import pytest
import urllib3

from homeassistant.components.http.security_filter import FILTERS, setup_security_filter
from homeassistant.components.http.server import MAX_LINE_SIZE

from tests.typing import ClientSessionGenerator


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
    request_path,
    request_params,
    fail_on_query_string,
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

    message = "Filtered a potential harmful request to:"
    if fail_on_query_string:
        message = "Filtered a request with a potential harmful query string:"
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
    request_path,
    request_params,
    fail_on_query_string,
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

    message = "Filtered a request with an unsafe byte in path:"
    if fail_on_query_string:
        message = "Filtered a request with unsafe byte query string:"
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
    assert "Filtered a potential harmful request to:" in caplog.text
