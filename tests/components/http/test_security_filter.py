"""Test security filter middleware."""

import asyncio
from http import HTTPStatus

from aiohttp import web
from aiohttp.test_utils import make_mocked_request
import pytest
import urllib3

from homeassistant.components.http.security_filter import setup_security_filter

from tests.typing import ClientSessionGenerator


async def mock_handler(request: web.Request) -> web.Response:
    """Return OK."""
    return web.Response(text="OK")


@pytest.mark.parametrize(
    ("request_path", "request_params"),
    [
        ("/", {}),
        ("/lovelace/dashboard", {}),
        ("/frontend_latest/chunk.4c9e2d8dc10f77b885b0.js", {}),
        ("/static/translations/en-f96a262a5a6eede29234dc45dc63abf2.json", {}),
        ("/", {"test": "123"}),
        ("/", {"some": "\thing"}),
        ("/", {"\newline": "cinema"}),
        ("/", {"return": "t\rue"}),
    ],
)
async def test_ok_requests(
    request_path: str,
    request_params: dict[str, str],
    aiohttp_client: ClientSessionGenerator,
) -> None:
    """Test request paths that should not be filtered."""
    app = web.Application()
    app.router.add_get("/{all:.*}", mock_handler)

    setup_security_filter(app)

    mock_api_client = await aiohttp_client(app)
    resp = await mock_api_client.get(request_path, params=request_params)

    assert resp.status == HTTPStatus.OK
    assert await resp.text() == "OK"


async def test_ok_request_with_encoded_unsafe_byte_in_query_string(
    aiohttp_client: ClientSessionGenerator,
) -> None:
    """Test an encoded unsafe byte remains a valid query-string value."""
    app = web.Application()
    app.router.add_get("/{all:.*}", mock_handler)

    setup_security_filter(app)

    mock_api_client = await aiohttp_client(app)
    resp = await mock_api_client.get("/?message=hello%0Aworld")

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
        ("/", {"sql": "UNION\nSELECT (a, b"}, True),
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

    message = "Filtered a potential harmful request to:"
    if fail_on_query_string:
        message = "Filtered a request with a potential harmful query string:"
    assert message in caplog.text


@pytest.mark.parametrize(
    "request_path",
    [
        "/some\thing",
        "/new\nline/cinema",
        "/new%0Aline/cinema",
        "/return\r/to/sender",
    ],
)
async def test_bad_requests_with_unsafe_bytes(
    request_path: str,
    aiohttp_client: ClientSessionGenerator,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test request with unsafe bytes in their URLs."""
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

    assert "Filtered a request with an unsafe byte in path:" in caplog.text


@pytest.mark.parametrize(
    "request_path",
    [
        "/?f=proc/self%0A/environ",
        "/?f=proc/self%250A/environ",
        "/?p=..%0A/..%0A/api",
        "/?x=/.%0A/test",
    ],
)
async def test_bad_requests_with_encoded_unsafe_bytes_in_filter_patterns(
    request_path: str,
    aiohttp_client: ClientSessionGenerator,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test encoded unsafe bytes cannot bypass security-filter patterns."""
    app = web.Application()
    app.router.add_get("/{all:.*}", mock_handler)

    setup_security_filter(app)

    mock_api_client = await aiohttp_client(app)
    resp = await mock_api_client.get(request_path)

    assert resp.status == HTTPStatus.BAD_REQUEST
    assert "Filtered a request with a potential harmful query string:" in caplog.text


@pytest.mark.parametrize("unsafe_byte", ["\t", "\r", "\n"])
async def test_bad_requests_with_literal_unsafe_bytes_in_query_string(
    unsafe_byte: str, caplog: pytest.LogCaptureFixture
) -> None:
    """Test requests with literal unsafe bytes in their query strings."""
    app = web.Application()
    setup_security_filter(app)

    request = make_mocked_request("GET", f"/?q=a{unsafe_byte}b", app=app)

    with pytest.raises(web.HTTPBadRequest):
        await app.middlewares[0](request, mock_handler)

    assert "Filtered a request with unsafe byte query string:" in caplog.text
