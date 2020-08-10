"""Test real forwarded middleware."""
from ipaddress import ip_network

from aiohttp import web
from aiohttp.hdrs import X_FORWARDED_FOR, X_FORWARDED_HOST, X_FORWARDED_PROTO

from homeassistant.components.http.forwarded import setup_forwarded


async def mock_handler(request):
    """Return the real IP as text."""
    return web.Response(text=request.remote)


async def test_x_forwarded_for_without_trusted_proxy(aiohttp_client):
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

    setup_forwarded(app, [])

    mock_api_client = await aiohttp_client(app)

    resp = await mock_api_client.get("/", headers={X_FORWARDED_FOR: "255.255.255.255"})
    assert resp.status == 200


async def test_x_forwarded_for_with_trusted_proxy(aiohttp_client):
    """Test that we get the IP from the forwarded for header."""

    async def handler(request):
        url = mock_api_client.make_url("/")
        assert request.host == f"{url.host}:{url.port}"
        assert request.scheme == "http"
        assert not request.secure
        assert request.remote == "255.255.255.255"

        return web.Response()

    app = web.Application()
    app.router.add_get("/", handler)
    setup_forwarded(app, [ip_network("127.0.0.1")])

    mock_api_client = await aiohttp_client(app)

    resp = await mock_api_client.get("/", headers={X_FORWARDED_FOR: "255.255.255.255"})
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
    setup_forwarded(app, [ip_network("1.1.1.1")])

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
    setup_forwarded(app, [ip_network("127.0.0.1")])

    mock_api_client = await aiohttp_client(app)

    resp = await mock_api_client.get(
        "/", headers={X_FORWARDED_FOR: "222.222.222.222, 255.255.255.255"}
    )
    assert resp.status == 200


async def test_x_forwarded_for_with_nonsense_header(aiohttp_client):
    """Test that we get a HTTP 400 bad request with a malformed header."""
    app = web.Application()
    app.router.add_get("/", mock_handler)
    setup_forwarded(app, [ip_network("127.0.0.1")])

    mock_api_client = await aiohttp_client(app)

    resp = await mock_api_client.get(
        "/", headers={X_FORWARDED_FOR: "This value is invalid"}
    )
    assert resp.status == 400

    resp = await mock_api_client.get(
        "/", headers={X_FORWARDED_FOR: "1.1.1.1, , 1.2.3.4"}
    )
    assert resp.status == 400

    resp = await mock_api_client.get(
        "/", headers={X_FORWARDED_FOR: "1.1.1.1, batman, 1.2.3.4"}
    )
    assert resp.status == 400


async def test_x_forwarded_for_with_multiple_headers(aiohttp_client):
    """Test that we get a HTTP 400 bad request with multiple headers."""
    app = web.Application()
    app.router.add_get("/", mock_handler)
    setup_forwarded(app, [ip_network("127.0.0.1")])

    mock_api_client = await aiohttp_client(app)

    resp = await mock_api_client.get(
        "/",
        headers=[
            (X_FORWARDED_FOR, "222.222.222.222"),
            (X_FORWARDED_FOR, "123.123.123.123"),
        ],
    )
    assert resp.status == 400


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
    setup_forwarded(app, [ip_network("127.0.0.1")])

    mock_api_client = await aiohttp_client(app)

    resp = await mock_api_client.get("/", headers={X_FORWARDED_PROTO: "https"})
    assert resp.status == 200


async def test_x_forwarded_proto_with_multiple_headers(aiohttp_client):
    """Test that we get a HTTP 400 bad request with multiple headers."""
    app = web.Application()
    app.router.add_get("/", mock_handler)
    setup_forwarded(app, [ip_network("127.0.0.1")])

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
    setup_forwarded(app, [ip_network("127.0.0.1")])

    mock_api_client = await aiohttp_client(app)

    resp = await mock_api_client.get("/", headers={X_FORWARDED_HOST: "example.com"})
    assert resp.status == 200


async def test_x_forwarded_host_with_multiple_headers(aiohttp_client):
    """Test that we get a HTTP 400 bad request with multiple headers."""
    app = web.Application()
    app.router.add_get("/", mock_handler)
    setup_forwarded(app, [ip_network("127.0.0.1")])

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
