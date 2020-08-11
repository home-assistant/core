"""Test real forwarded middleware."""
from ipaddress import ip_network

from aiohttp import web
from aiohttp.hdrs import X_FORWARDED_FOR, X_FORWARDED_HOST, X_FORWARDED_PROTO
import pytest

from homeassistant.components.http.forwarded import async_setup_forwarded


async def mock_handler(request):
    """Return the real IP as text."""
    return web.Response(text=request.remote)


async def test_x_forwarded_for_without_trusted_proxy(aiohttp_client, caplog):
    """Test that we get the IP from the transport."""

    async def handler(request):
        url = mock_api_client.make_url("/")
        assert request.host == f"{url.host}:{url.port}"
        assert request.scheme == "http"
        assert not request.secure
        assert request.remote == "127.0.0.1"

        return web.Response()

    app = web.Application()
    app.router.add_get("/", handler)

    async_setup_forwarded(app, [])

    mock_api_client = await aiohttp_client(app)
    resp = await mock_api_client.get("/", headers={X_FORWARDED_FOR: "255.255.255.255"})

    assert resp.status == 200
    assert (
        "Received X-Forwarded-For header from untrusted proxy 127.0.0.1, headers not processed"
        in caplog.text
    )


@pytest.mark.parametrize(
    "trusted_proxies,x_forwarded_for,remote",
    [
        (
            ["127.0.0.0/24", "1.1.1.1", "10.10.10.0/24"],
            "10.10.10.10, 1.1.1.1",
            "10.10.10.10",
        ),
        (["127.0.0.0/24", "1.1.1.1"], "123.123.123.123, 2.2.2.2, 1.1.1.1", "2.2.2.2"),
        (["127.0.0.0/24", "1.1.1.1"], "123.123.123.123,2.2.2.2,1.1.1.1", "2.2.2.2"),
        (["127.0.0.0/24"], "123.123.123.123, 2.2.2.2, 1.1.1.1", "1.1.1.1"),
        (["127.0.0.0/24"], "127.0.0.1", "127.0.0.1"),
        (["127.0.0.1", "1.1.1.1"], "123.123.123.123, 1.1.1.1", "123.123.123.123"),
        (["127.0.0.1", "1.1.1.1"], "123.123.123.123, 2.2.2.2, 1.1.1.1", "2.2.2.2"),
        (["127.0.0.1"], "255.255.255.255", "255.255.255.255"),
    ],
)
async def test_x_forwarded_for_with_trusted_proxy(
    trusted_proxies, x_forwarded_for, remote, aiohttp_client
):
    """Test that we get the IP from the forwarded for header."""

    async def handler(request):
        url = mock_api_client.make_url("/")
        assert request.host == f"{url.host}:{url.port}"
        assert request.scheme == "http"
        assert not request.secure
        assert request.remote == remote

        return web.Response()

    app = web.Application()
    app.router.add_get("/", handler)
    async_setup_forwarded(
        app, [ip_network(trusted_proxy) for trusted_proxy in trusted_proxies]
    )

    mock_api_client = await aiohttp_client(app)
    resp = await mock_api_client.get("/", headers={X_FORWARDED_FOR: x_forwarded_for})

    assert resp.status == 200


async def test_x_forwarded_for_with_untrusted_proxy(aiohttp_client):
    """Test that we get the IP from transport with untrusted proxy."""

    async def handler(request):
        url = mock_api_client.make_url("/")
        assert request.host == f"{url.host}:{url.port}"
        assert request.scheme == "http"
        assert not request.secure
        assert request.remote == "127.0.0.1"

        return web.Response()

    app = web.Application()
    app.router.add_get("/", handler)
    async_setup_forwarded(app, [ip_network("1.1.1.1")])

    mock_api_client = await aiohttp_client(app)
    resp = await mock_api_client.get("/", headers={X_FORWARDED_FOR: "255.255.255.255"})

    assert resp.status == 200


async def test_x_forwarded_for_with_spoofed_header(aiohttp_client):
    """Test that we get the IP from the transport with a spoofed header."""

    async def handler(request):
        url = mock_api_client.make_url("/")
        assert request.host == f"{url.host}:{url.port}"
        assert request.scheme == "http"
        assert not request.secure
        assert request.remote == "255.255.255.255"

        return web.Response()

    app = web.Application()
    app.router.add_get("/", handler)
    async_setup_forwarded(app, [ip_network("127.0.0.1")])

    mock_api_client = await aiohttp_client(app)
    resp = await mock_api_client.get(
        "/", headers={X_FORWARDED_FOR: "222.222.222.222, 255.255.255.255"}
    )

    assert resp.status == 200


@pytest.mark.parametrize(
    "x_forwarded_for",
    [
        "This value is invalid",
        "1.1.1.1, , 1.2.3.4",
        "1.1.1.1,,1.2.3.4",
        "1.1.1.1, batman, 1.2.3.4",
        "192.168.0.0/24",
        "192.168.0.0/24, 1.1.1.1",
        ",",
        "",
    ],
)
async def test_x_forwarded_for_with_malformed_header(
    x_forwarded_for, aiohttp_client, caplog
):
    """Test that we get a HTTP 400 bad request with a malformed header."""
    app = web.Application()
    app.router.add_get("/", mock_handler)
    async_setup_forwarded(app, [ip_network("127.0.0.1")])

    mock_api_client = await aiohttp_client(app)

    resp = await mock_api_client.get("/", headers={X_FORWARDED_FOR: x_forwarded_for})

    assert resp.status == 400
    assert "Invalid IP address in X-Forwarded-For" in caplog.text


async def test_x_forwarded_for_with_multiple_headers(aiohttp_client, caplog):
    """Test that we get a HTTP 400 bad request with multiple headers."""
    app = web.Application()
    app.router.add_get("/", mock_handler)
    async_setup_forwarded(app, [ip_network("127.0.0.1")])

    mock_api_client = await aiohttp_client(app)

    resp = await mock_api_client.get(
        "/",
        headers=[
            (X_FORWARDED_FOR, "222.222.222.222"),
            (X_FORWARDED_FOR, "123.123.123.123"),
        ],
    )

    assert resp.status == 400
    assert "Too many headers for X-Forwarded-For" in caplog.text


async def test_x_forwarded_proto_without_trusted_proxy(aiohttp_client):
    """Test that proto header is ignored when untrusted."""

    async def handler(request):
        url = mock_api_client.make_url("/")
        assert request.host == f"{url.host}:{url.port}"
        assert request.scheme == "http"
        assert not request.secure
        assert request.remote == "127.0.0.1"

        return web.Response()

    app = web.Application()
    app.router.add_get("/", handler)

    async_setup_forwarded(app, [])

    mock_api_client = await aiohttp_client(app)
    resp = await mock_api_client.get(
        "/", headers={X_FORWARDED_FOR: "255.255.255.255", X_FORWARDED_PROTO: "https"}
    )

    assert resp.status == 200


@pytest.mark.parametrize(
    "x_forwarded_for,remote,x_forwarded_proto,secure",
    [
        ("10.10.10.10, 127.0.0.1, 127.0.0.2", "10.10.10.10", "https, http, http", True),
        ("10.10.10.10, 127.0.0.1, 127.0.0.2", "10.10.10.10", "https,http,http", True),
        ("10.10.10.10, 127.0.0.1, 127.0.0.2", "10.10.10.10", "http", False),
        (
            "10.10.10.10, 127.0.0.1, 127.0.0.2",
            "10.10.10.10",
            "http, https, https",
            False,
        ),
        ("10.10.10.10, 127.0.0.1, 127.0.0.2", "10.10.10.10", "https", True),
        (
            "255.255.255.255, 10.10.10.10, 127.0.0.1",
            "10.10.10.10",
            "http, https, http",
            True,
        ),
        (
            "255.255.255.255, 10.10.10.10, 127.0.0.1",
            "10.10.10.10",
            "https, http, https",
            False,
        ),
        ("255.255.255.255, 10.10.10.10, 127.0.0.1", "10.10.10.10", "https", True),
    ],
)
async def test_x_forwarded_proto_with_trusted_proxy(
    x_forwarded_for, remote, x_forwarded_proto, secure, aiohttp_client
):
    """Test that we get the proto header if proxy is trusted."""

    async def handler(request):
        assert request.remote == remote
        assert request.scheme == ("https" if secure else "http")
        assert request.secure == secure

        return web.Response()

    app = web.Application()
    app.router.add_get("/", handler)
    async_setup_forwarded(app, [ip_network("127.0.0.0/24")])

    mock_api_client = await aiohttp_client(app)
    resp = await mock_api_client.get(
        "/",
        headers={
            X_FORWARDED_FOR: x_forwarded_for,
            X_FORWARDED_PROTO: x_forwarded_proto,
        },
    )

    assert resp.status == 200


async def test_x_forwarded_proto_with_trusted_proxy_multiple_for(aiohttp_client):
    """Test that we get the proto with 1 element in the proto, multiple in the for."""

    async def handler(request):
        url = mock_api_client.make_url("/")
        assert request.host == f"{url.host}:{url.port}"
        assert request.scheme == "https"
        assert request.secure
        assert request.remote == "255.255.255.255"

        return web.Response()

    app = web.Application()
    app.router.add_get("/", handler)
    async_setup_forwarded(app, [ip_network("127.0.0.0/24")])

    mock_api_client = await aiohttp_client(app)
    resp = await mock_api_client.get(
        "/",
        headers={
            X_FORWARDED_FOR: "255.255.255.255, 127.0.0.1, 127.0.0.2",
            X_FORWARDED_PROTO: "https",
        },
    )

    assert resp.status == 200


async def test_x_forwarded_proto_not_processed_without_for(aiohttp_client):
    """Test that proto header isn't processed without a for header."""

    async def handler(request):
        url = mock_api_client.make_url("/")
        assert request.host == f"{url.host}:{url.port}"
        assert request.scheme == "http"
        assert not request.secure
        assert request.remote == "127.0.0.1"

        return web.Response()

    app = web.Application()
    app.router.add_get("/", handler)
    async_setup_forwarded(app, [ip_network("127.0.0.1")])

    mock_api_client = await aiohttp_client(app)
    resp = await mock_api_client.get("/", headers={X_FORWARDED_PROTO: "https"})

    assert resp.status == 200


async def test_x_forwarded_proto_with_multiple_headers(aiohttp_client, caplog):
    """Test that we get a HTTP 400 bad request with multiple headers."""
    app = web.Application()
    app.router.add_get("/", mock_handler)
    async_setup_forwarded(app, [ip_network("127.0.0.1")])

    mock_api_client = await aiohttp_client(app)
    resp = await mock_api_client.get(
        "/",
        headers=[
            (X_FORWARDED_FOR, "222.222.222.222"),
            (X_FORWARDED_PROTO, "https"),
            (X_FORWARDED_PROTO, "http"),
        ],
    )

    assert resp.status == 400
    assert "Too many headers for X-Forward-Proto" in caplog.text


@pytest.mark.parametrize(
    "x_forwarded_proto", ["", ",", "https, , https", "https, https, "],
)
async def test_x_forwarded_proto_empty_element(
    x_forwarded_proto, aiohttp_client, caplog
):
    """Test that we get a HTTP 400 bad request with empty proto."""
    app = web.Application()
    app.router.add_get("/", mock_handler)
    async_setup_forwarded(app, [ip_network("127.0.0.1")])

    mock_api_client = await aiohttp_client(app)
    resp = await mock_api_client.get(
        "/", headers={X_FORWARDED_FOR: "1.1.1.1", X_FORWARDED_PROTO: x_forwarded_proto},
    )

    assert resp.status == 400
    assert "Empty item received in X-Forward-Proto header" in caplog.text


@pytest.mark.parametrize(
    "x_forwarded_for,x_forwarded_proto,expected,got",
    [
        ("1.1.1.1, 2.2.2.2", "https, https, https", 2, 3),
        ("1.1.1.1, 2.2.2.2, 3.3.3.3, 4.4.4.4", "https, https, https", 4, 3),
    ],
)
async def test_x_forwarded_proto_incorrect_number_of_elements(
    x_forwarded_for, x_forwarded_proto, expected, got, aiohttp_client, caplog
):
    """Test that we get a HTTP 400 bad request with incorrect number of elements."""
    app = web.Application()
    app.router.add_get("/", mock_handler)
    async_setup_forwarded(app, [ip_network("127.0.0.1")])

    mock_api_client = await aiohttp_client(app)
    resp = await mock_api_client.get(
        "/",
        headers={
            X_FORWARDED_FOR: x_forwarded_for,
            X_FORWARDED_PROTO: x_forwarded_proto,
        },
    )

    assert resp.status == 400
    assert (
        f"Incorrect number of elements in X-Forward-Proto. Expected 1 or {expected}, got {got}"
        in caplog.text
    )


async def test_x_forwarded_host_without_trusted_proxy(aiohttp_client):
    """Test that host header is ignored when untrusted."""

    async def handler(request):
        url = mock_api_client.make_url("/")
        assert request.host == f"{url.host}:{url.port}"
        assert request.scheme == "http"
        assert not request.secure
        assert request.remote == "127.0.0.1"

        return web.Response()

    app = web.Application()
    app.router.add_get("/", handler)

    async_setup_forwarded(app, [])

    mock_api_client = await aiohttp_client(app)
    resp = await mock_api_client.get(
        "/",
        headers={X_FORWARDED_FOR: "255.255.255.255", X_FORWARDED_HOST: "example.com"},
    )

    assert resp.status == 200


async def test_x_forwarded_host_with_trusted_proxy(aiohttp_client):
    """Test that we get the host header if proxy is trusted."""

    async def handler(request):
        assert request.host == "example.com"
        assert request.scheme == "http"
        assert not request.secure
        assert request.remote == "255.255.255.255"

        return web.Response()

    app = web.Application()
    app.router.add_get("/", handler)
    async_setup_forwarded(app, [ip_network("127.0.0.1")])

    mock_api_client = await aiohttp_client(app)
    resp = await mock_api_client.get(
        "/",
        headers={X_FORWARDED_FOR: "255.255.255.255", X_FORWARDED_HOST: "example.com"},
    )

    assert resp.status == 200


async def test_x_forwarded_host_not_processed_without_for(aiohttp_client):
    """Test that host header isn't processed without a for header."""

    async def handler(request):
        url = mock_api_client.make_url("/")
        assert request.host == f"{url.host}:{url.port}"
        assert request.scheme == "http"
        assert not request.secure
        assert request.remote == "127.0.0.1"

        return web.Response()

    app = web.Application()
    app.router.add_get("/", handler)
    async_setup_forwarded(app, [ip_network("127.0.0.1")])

    mock_api_client = await aiohttp_client(app)
    resp = await mock_api_client.get("/", headers={X_FORWARDED_HOST: "example.com"})

    assert resp.status == 200


async def test_x_forwarded_host_with_multiple_headers(aiohttp_client, caplog):
    """Test that we get a HTTP 400 bad request with multiple headers."""
    app = web.Application()
    app.router.add_get("/", mock_handler)
    async_setup_forwarded(app, [ip_network("127.0.0.1")])

    mock_api_client = await aiohttp_client(app)
    resp = await mock_api_client.get(
        "/",
        headers=[
            (X_FORWARDED_FOR, "222.222.222.222"),
            (X_FORWARDED_HOST, "example.com"),
            (X_FORWARDED_HOST, "example.spoof"),
        ],
    )

    assert resp.status == 400
    assert "Too many headers for X-Forwarded-Host" in caplog.text


async def test_x_forwarded_host_with_empty_header(aiohttp_client, caplog):
    """Test that we get a HTTP 400 bad request with empty host value."""
    app = web.Application()
    app.router.add_get("/", mock_handler)
    async_setup_forwarded(app, [ip_network("127.0.0.1")])

    mock_api_client = await aiohttp_client(app)
    resp = await mock_api_client.get(
        "/", headers={X_FORWARDED_FOR: "222.222.222.222", X_FORWARDED_HOST: ""}
    )

    assert resp.status == 400
    assert "Empty value received in X-Forward-Host header" in caplog.text
