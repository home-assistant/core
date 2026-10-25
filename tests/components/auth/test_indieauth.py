"""Tests for the client validator."""

import asyncio
import json
from unittest.mock import patch

import aiohttp
import pytest
from pytest_homeassistant.test_util.aiohttp import AiohttpClientMocker

from homeassistant.components.auth import indieauth
from homeassistant.core import HomeAssistant

REQUEST_SCHEME = "https"
REQUEST_NETLOC = "homeassistant.example"


@pytest.fixture
def mock_session():
    """Mock aiohttp.ClientSession."""
    mocker = AiohttpClientMocker()

    with patch(
        "aiohttp.ClientSession",
        side_effect=lambda *args, **kwargs: mocker.create_session(
            asyncio.get_event_loop()
        ),
    ):
        yield mocker


def test_client_id_scheme() -> None:
    """Test we enforce valid scheme."""
    assert indieauth._parse_client_id(
        "http://ex.com/", request_scheme=REQUEST_SCHEME, request_netloc=REQUEST_NETLOC
    )
    assert indieauth._parse_client_id(
        "https://ex.com/", request_scheme=REQUEST_SCHEME, request_netloc=REQUEST_NETLOC
    )

    with pytest.raises(ValueError):
        indieauth._parse_client_id(
            "ftp://ex.com", request_scheme=REQUEST_SCHEME, request_netloc=REQUEST_NETLOC
        )


def test_client_id_path() -> None:
    """Test we enforce valid path."""
    assert (
        indieauth._parse_client_id(
            "http://ex.com",
            request_scheme=REQUEST_SCHEME,
            request_netloc=REQUEST_NETLOC,
        ).path
        == "/"
    )
    assert (
        indieauth._parse_client_id(
            "http://ex.com/hello",
            request_scheme=REQUEST_SCHEME,
            request_netloc=REQUEST_NETLOC,
        ).path
        == "/hello"
    )
    assert (
        indieauth._parse_client_id(
            "http://ex.com/hello/.world",
            request_scheme=REQUEST_SCHEME,
            request_netloc=REQUEST_NETLOC,
        ).path
        == "/hello/.world"
    )
    assert (
        indieauth._parse_client_id(
            "http://ex.com/hello./.world",
            request_scheme=REQUEST_SCHEME,
            request_netloc=REQUEST_NETLOC,
        ).path
        == "/hello./.world"
    )

    with pytest.raises(ValueError):
        indieauth._parse_client_id(
            "http://ex.com/.",
            request_scheme=REQUEST_SCHEME,
            request_netloc=REQUEST_NETLOC,
        )

    with pytest.raises(ValueError):
        indieauth._parse_client_id(
            "http://ex.com/hello/./yo",
            request_scheme=REQUEST_SCHEME,
            request_netloc=REQUEST_NETLOC,
        )

    with pytest.raises(ValueError):
        indieauth._parse_client_id(
            "http://ex.com/hello/../yo",
            request_scheme=REQUEST_SCHEME,
            request_netloc=REQUEST_NETLOC,
        )


def test_client_id_fragment() -> None:
    """Test we enforce valid fragment."""
    with pytest.raises(ValueError):
        indieauth._parse_client_id(
            "http://ex.com/#yoo",
            request_scheme=REQUEST_SCHEME,
            request_netloc=REQUEST_NETLOC,
        )


def test_client_id_user_pass() -> None:
    """Test we enforce valid username/password."""
    with pytest.raises(ValueError):
        indieauth._parse_client_id(
            "http://user@ex.com/",
            request_scheme=REQUEST_SCHEME,
            request_netloc=REQUEST_NETLOC,
        )

    with pytest.raises(ValueError):
        indieauth._parse_client_id(
            "http://user:pass@ex.com/",
            request_scheme=REQUEST_SCHEME,
            request_netloc=REQUEST_NETLOC,
        )


def test_client_id_hostname() -> None:
    """Test we enforce valid hostname."""
    assert indieauth._parse_client_id(
        "http://www.home-assistant.io/",
        request_scheme=REQUEST_SCHEME,
        request_netloc=REQUEST_NETLOC,
    )
    assert indieauth._parse_client_id(
        "http://[::1]", request_scheme=REQUEST_SCHEME, request_netloc=REQUEST_NETLOC
    )
    assert indieauth._parse_client_id(
        "http://[::1]:8123/",
        request_scheme=REQUEST_SCHEME,
        request_netloc=REQUEST_NETLOC,
    )
    assert indieauth._parse_client_id(
        "http://[fe80::1]:8123/",
        request_scheme=REQUEST_SCHEME,
        request_netloc=REQUEST_NETLOC,
    )
    assert indieauth._parse_client_id(
        "http://127.0.0.1", request_scheme=REQUEST_SCHEME, request_netloc=REQUEST_NETLOC
    )
    assert indieauth._parse_client_id(
        "http://10.0.0.0", request_scheme=REQUEST_SCHEME, request_netloc=REQUEST_NETLOC
    )
    assert indieauth._parse_client_id(
        "http://10.255.255.255",
        request_scheme=REQUEST_SCHEME,
        request_netloc=REQUEST_NETLOC,
    )
    assert indieauth._parse_client_id(
        "http://172.16.0.0",
        request_scheme=REQUEST_SCHEME,
        request_netloc=REQUEST_NETLOC,
    )
    assert indieauth._parse_client_id(
        "http://172.31.255.255",
        request_scheme=REQUEST_SCHEME,
        request_netloc=REQUEST_NETLOC,
    )
    assert indieauth._parse_client_id(
        "http://192.168.0.0",
        request_scheme=REQUEST_SCHEME,
        request_netloc=REQUEST_NETLOC,
    )
    assert indieauth._parse_client_id(
        "http://192.168.255.255",
        request_scheme=REQUEST_SCHEME,
        request_netloc=REQUEST_NETLOC,
    )

    with pytest.raises(ValueError):
        assert indieauth._parse_client_id(
            "http://255.255.255.255/",
            request_scheme=REQUEST_SCHEME,
            request_netloc=REQUEST_NETLOC,
        )
    with pytest.raises(ValueError):
        assert indieauth._parse_client_id(
            "http://11.0.0.0/",
            request_scheme=REQUEST_SCHEME,
            request_netloc=REQUEST_NETLOC,
        )
    with pytest.raises(ValueError):
        assert indieauth._parse_client_id(
            "http://172.32.0.0/",
            request_scheme=REQUEST_SCHEME,
            request_netloc=REQUEST_NETLOC,
        )
    with pytest.raises(ValueError):
        assert indieauth._parse_client_id(
            "http://192.167.0.0/",
            request_scheme=REQUEST_SCHEME,
            request_netloc=REQUEST_NETLOC,
        )
    with pytest.raises(ValueError):
        assert indieauth._parse_client_id(
            "http://8.8.8.8:8123/",
            request_scheme=REQUEST_SCHEME,
            request_netloc=REQUEST_NETLOC,
        )
    with pytest.raises(ValueError):
        assert indieauth._parse_client_id(
            "http://[2001:db8::1]/",
            request_scheme=REQUEST_SCHEME,
            request_netloc=REQUEST_NETLOC,
        )
    with pytest.raises(ValueError):
        assert indieauth._parse_client_id(
            "http://[2001:db8::1]:8123/",
            request_scheme=REQUEST_SCHEME,
            request_netloc=REQUEST_NETLOC,
        )
    with pytest.raises(ValueError):
        assert indieauth._parse_client_id(
            "http://", request_scheme=REQUEST_SCHEME, request_netloc=REQUEST_NETLOC
        )
    with pytest.raises(ValueError):
        assert indieauth._parse_client_id(
            "https:///callback",
            request_scheme=REQUEST_SCHEME,
            request_netloc=REQUEST_NETLOC,
        )
    with pytest.raises(ValueError):
        assert indieauth._parse_client_id(
            "http://:8123/",
            request_scheme=REQUEST_SCHEME,
            request_netloc=REQUEST_NETLOC,
        )


@pytest.mark.parametrize(
    ("client_id", "request_scheme", "request_netloc"),
    [
        pytest.param("http://[2001:db8::1]/", "http", "[2001:db8::1]", id="ipv6"),
        pytest.param(
            "http://[2001:db8::1]/", "http", "[2001:DB8::1]", id="ipv6-uppercase"
        ),
        pytest.param("http://100.64.1.1/", "http", "100.64.1.1", id="tailscale"),
        pytest.param(
            "http://192.168.1.10:8123/", "http", "192.168.1.10:8123", id="private"
        ),
        pytest.param(
            "http://100.64.1.1/", "http", "100.64.1.1:80", id="http-default-port"
        ),
        pytest.param(
            "https://[2001:db8::1]/",
            "https",
            "[2001:db8::1]:443",
            id="https-default-port",
        ),
        pytest.param(
            "http://100.64.1.1:80/", "http", "100.64.1.1", id="client-id-default-port"
        ),
        pytest.param(
            "http://[2001:db8::1]/", "http", "[2001:db8:0:0::1]", id="ipv6-notation"
        ),
        pytest.param(
            "https://203.0.113.5:8443/", "https", "203.0.113.5:8443", id="port"
        ),
    ],
)
def test_client_id_request_origin_allowed(
    client_id: str, request_scheme: str, request_netloc: str
) -> None:
    """Test a public IP is allowed when it matches the request origin."""
    assert indieauth.verify_client_id(
        client_id, request_scheme=request_scheme, request_netloc=request_netloc
    )


@pytest.mark.parametrize(
    ("client_id", "request_scheme", "request_netloc"),
    [
        pytest.param("http://[2001:db8::1]/", "http", "[2001:db8::2]", id="host"),
        pytest.param("http://100.64.1.1/", "https", "100.64.1.1", id="scheme"),
        pytest.param("http://203.0.113.5:8443/", "http", "203.0.113.5:9000", id="port"),
        pytest.param(
            "http://100.64.1.1/", "http", "100.64.1.1:443", id="other-default-port"
        ),
        pytest.param(
            "https://100.64.1.1/", "https", "100.64.1.1:80", id="https-port-80"
        ),
        pytest.param("http://100.64.1.1/", "http", "100.64.1.1:abc", id="invalid-port"),
        pytest.param("http://100.64.1.1/", "http", "user@100.64.1.1", id="username"),
        pytest.param(
            "http://100.64.1.1:0/", "http", "100.64.1.1", id="client-id-port-0"
        ),
        pytest.param("http://100.64.1.1/", "http", "100.64.1.1:0", id="request-port-0"),
        pytest.param("http://100.64.1.1/", "http", "ha.example.com", id="domain"),
    ],
)
def test_client_id_request_origin_mismatch(
    client_id: str, request_scheme: str, request_netloc: str
) -> None:
    """Test a public IP is rejected when it does not match the request origin."""
    assert not indieauth.verify_client_id(
        client_id, request_scheme=request_scheme, request_netloc=request_netloc
    )


def test_parse_url_lowercase_host() -> None:
    """Test we update empty paths."""
    assert indieauth._parse_url("http://ex.com/hello").path == "/hello"
    assert indieauth._parse_url("http://EX.COM/hello").hostname == "ex.com"

    parts = indieauth._parse_url("http://EX.COM:123/HELLO")
    assert parts.netloc == "ex.com:123"
    assert parts.path == "/HELLO"


def test_parse_url_path() -> None:
    """Test we update empty paths."""
    assert indieauth._parse_url("http://ex.com").path == "/"


async def test_verify_redirect_uri() -> None:
    """Test that we verify redirect uri correctly."""
    assert await indieauth.verify_redirect_uri(
        None,
        "http://ex.com",
        "http://ex.com/callback",
        request_scheme=REQUEST_SCHEME,
        request_netloc=REQUEST_NETLOC,
    )

    with patch.object(indieauth, "fetch_redirect_uris", return_value=[]):
        # Different domain
        assert not await indieauth.verify_redirect_uri(
            None,
            "http://ex.com",
            "http://different.com/callback",
            request_scheme=REQUEST_SCHEME,
            request_netloc=REQUEST_NETLOC,
        )

        # Different scheme
        assert not await indieauth.verify_redirect_uri(
            None,
            "http://ex.com",
            "https://ex.com/callback",
            request_scheme=REQUEST_SCHEME,
            request_netloc=REQUEST_NETLOC,
        )

        # Different subdomain
        assert not await indieauth.verify_redirect_uri(
            None,
            "https://sub1.ex.com",
            "https://sub2.ex.com/callback",
            request_scheme=REQUEST_SCHEME,
            request_netloc=REQUEST_NETLOC,
        )


async def test_find_link_tag(hass: HomeAssistant, mock_session) -> None:
    """Test finding link tag."""
    mock_session.get(
        "http://127.0.0.1:8000",
        text="""
<!doctype html>
<html>
  <head>
    <link rel="redirect_uri" href="hass://oauth2_redirect">
    <link rel="other_value" href="hass://oauth2_redirect">
    <link rel="redirect_uri" href="/beer">
  </head>
  ...
</html>
""",
    )
    redirect_uris = await indieauth.fetch_redirect_uris(hass, "http://127.0.0.1:8000")

    assert redirect_uris == ["hass://oauth2_redirect", "http://127.0.0.1:8000/beer"]


async def test_find_link_tag_max_size(hass: HomeAssistant, mock_session) -> None:
    """Test finding link tag."""
    text = "".join(
        [
            '<link rel="redirect_uri" href="/wine">',
            ("0" * 1024 * 10),
            '<link rel="redirect_uri" href="/beer">',
        ]
    )
    mock_session.get("http://127.0.0.1:8000", text=text)
    redirect_uris = await indieauth.fetch_redirect_uris(hass, "http://127.0.0.1:8000")

    assert redirect_uris == ["http://127.0.0.1:8000/wine"]


async def test_find_link_tag_without_href(
    hass: HomeAssistant, mock_session: AiohttpClientMocker
) -> None:
    """Test a redirect_uri link tag without a usable href is skipped."""
    mock_session.get(
        "http://127.0.0.1:8000",
        text="""
<!doctype html>
<html>
  <head>
    <link rel="redirect_uri">
    <link rel="redirect_uri" href="">
    <link rel="redirect_uri" href="https://example.com/cb">
  </head>
</html>
""",
    )
    redirect_uris = await indieauth.fetch_redirect_uris(hass, "http://127.0.0.1:8000")

    assert redirect_uris == ["https://example.com/cb"]


async def test_fetch_redirect_uris_metadata_document(
    hass: HomeAssistant, mock_session: AiohttpClientMocker
) -> None:
    """Test fetching redirect uris from a client id metadata document."""
    mock_session.get(
        "https://example.com/client",
        text=json.dumps(
            {
                "client_id": "https://example.com/client",
                "redirect_uris": [
                    "https://example.com/callback",
                    "https://other.com/callback",
                ],
            }
        ),
        headers={"Content-Type": "application/json"},
    )
    redirect_uris = await indieauth.fetch_redirect_uris(
        hass, "https://example.com/client"
    )

    assert redirect_uris == [
        "https://example.com/callback",
        "https://other.com/callback",
    ]


async def test_fetch_redirect_uris_metadata_document_text_plain(
    hass: HomeAssistant, mock_session: AiohttpClientMocker
) -> None:
    """Test the metadata document is parsed regardless of content type."""
    mock_session.get(
        "https://example.com/client",
        text=json.dumps(
            {
                "client_id": "https://example.com/client",
                "redirect_uris": ["https://example.com/callback"],
            }
        ),
        headers={"Content-Type": "text/plain"},
    )
    redirect_uris = await indieauth.fetch_redirect_uris(
        hass, "https://example.com/client"
    )

    assert redirect_uris == ["https://example.com/callback"]


async def test_fetch_redirect_uris_link_tag_precedence(
    hass: HomeAssistant, mock_session: AiohttpClientMocker
) -> None:
    """Test link tags take precedence over metadata document parsing."""
    mock_session.get(
        "http://127.0.0.1:8000",
        text="""
<!doctype html>
<html>
  <head>
    <link rel="redirect_uri" href="hass://oauth2_redirect">
  </head>
  <body>
    {"redirect_uris": ["https://example.com/should-be-ignored"]}
  </body>
</html>
""",
    )
    redirect_uris = await indieauth.fetch_redirect_uris(hass, "http://127.0.0.1:8000")

    assert redirect_uris == ["hass://oauth2_redirect"]


@pytest.mark.parametrize(
    "text",
    [
        pytest.param("this is neither json nor html", id="not-json-not-html"),
        pytest.param('["https://example.com/callback"]', id="json-array"),
        pytest.param("42", id="json-scalar"),
        pytest.param(
            json.dumps({"redirect_uris": ["https://example.com/callback"]}),
            id="missing-client-id",
        ),
        pytest.param(
            json.dumps({"client_id": "https://example.com/client"}),
            id="missing-redirect-uris",
        ),
        pytest.param(
            json.dumps(
                {
                    "client_id": "https://example.com/client",
                    "redirect_uris": [],
                }
            ),
            id="empty-redirect-uris",
        ),
        pytest.param(
            json.dumps(
                {
                    "client_id": "https://other.example/client",
                    "redirect_uris": ["https://example.com/callback"],
                }
            ),
            id="client-id-mismatch",
        ),
        pytest.param(
            json.dumps(
                {
                    "client_id": "https://example.com/client",
                    "redirect_uris": "https://example.com/callback",
                }
            ),
            id="redirect-uris-not-list",
        ),
        pytest.param(
            json.dumps(
                {
                    "client_id": "https://example.com/client",
                    "redirect_uris": ["https://example.com/callback", 123],
                }
            ),
            id="redirect-uris-non-string-entry",
        ),
        pytest.param(
            json.dumps(
                {
                    "client_id": "https://example.com/client",
                    "redirect_uris": ["/callback"],
                }
            ),
            id="redirect-uris-relative-entry",
        ),
        pytest.param(
            json.dumps(
                {
                    "client_id": "https://example.com/client",
                    "redirect_uris": ["https://example.com/callback#fragment"],
                }
            ),
            id="redirect-uris-fragment-entry",
        ),
        pytest.param(
            json.dumps(
                {
                    "client_id": "https://example.com/client",
                    "redirect_uris": ["https://["],
                }
            ),
            id="redirect-uris-unparsable-entry",
        ),
        pytest.param(
            json.dumps(
                {
                    "client_id": "https://example.com/client",
                    "redirect_uris": ["https://example.com/callback#"],
                }
            ),
            id="redirect-uris-empty-fragment-entry",
        ),
        pytest.param(
            json.dumps(
                {
                    "client_id": "https://example.com/client",
                    "redirect_uris": ["https://example.com:not-a-port/callback"],
                }
            ),
            id="redirect-uris-invalid-port-entry",
        ),
        pytest.param(
            '{"client_id": "https://example.com/client",'
            ' "redirect_uris": ["https://example.com/callback"], "x": NaN}',
            id="json-nan-constant",
        ),
    ],
)
async def test_fetch_redirect_uris_metadata_document_invalid(
    hass: HomeAssistant, mock_session: AiohttpClientMocker, text: str
) -> None:
    """Test that invalid metadata documents yield no redirect uris."""
    mock_session.get(
        "https://example.com/client",
        text=text,
        headers={"Content-Type": "application/json"},
    )

    assert await indieauth.fetch_redirect_uris(hass, "https://example.com/client") == []
    assert not await indieauth.verify_redirect_uri(
        hass,
        "https://example.com/client",
        "https://other.com/callback",
        request_scheme=REQUEST_SCHEME,
        request_netloc=REQUEST_NETLOC,
    )


async def test_verify_redirect_uri_metadata_document(
    hass: HomeAssistant, mock_session: AiohttpClientMocker
) -> None:
    """Test verifying a cross-origin redirect uri from a metadata document."""
    client_id = "https://example.com/client"
    mock_session.get(
        client_id,
        text=json.dumps(
            {
                "client_id": client_id,
                "redirect_uris": ["https://other.com/callback"],
            }
        ),
        headers={"Content-Type": "application/json"},
    )

    assert await indieauth.verify_redirect_uri(
        hass,
        client_id,
        "https://other.com/callback",
        request_scheme=REQUEST_SCHEME,
        request_netloc=REQUEST_NETLOC,
    )

    assert not await indieauth.verify_redirect_uri(
        hass,
        client_id,
        "https://other.com/not-listed",
        request_scheme=REQUEST_SCHEME,
        request_netloc=REQUEST_NETLOC,
    )


async def test_verify_redirect_uri_unparsable(hass: HomeAssistant) -> None:
    """Test an unparsable requested redirect uri is rejected without raising."""
    assert not await indieauth.verify_redirect_uri(
        hass,
        "https://example.com/client",
        "https://[",
        request_scheme=REQUEST_SCHEME,
        request_netloc=REQUEST_NETLOC,
    )


@pytest.mark.parametrize(
    ("client_id", "registered_uri", "redirect_uri"),
    [
        pytest.param(
            "https://chatgpt.com/oauth/codex/example/client.json",
            "http://127.0.0.1/callback/example",
            "http://127.0.0.1:37545/callback/example",
            id="codex",
        ),
        pytest.param(
            "https://claude.ai/oauth/claude-code-client-metadata",
            "http://localhost/callback",
            "http://localhost:59019/callback",
            id="claude-code",
        ),
        pytest.param(
            "https://example.com/client",
            "http://[::1]/callback",
            "http://[::1]:12345/callback",
            id="ipv6",
        ),
        pytest.param(
            "https://example.com/client",
            "http://127.0.0.1:12345/callback?client=example",
            "http://127.0.0.1:54321/callback?client=example",
            id="registered-port-and-query",
        ),
        pytest.param(
            "https://example.com/client",
            "HTTP://localhost/callback",
            "HTTP://localhost:12345/callback",
            id="uppercase-scheme",
        ),
        pytest.param(
            "https://example.com/client",
            "HtTp://localhost:12345/callback",
            "HtTp://localhost:54321/callback",
            id="mixed-case-scheme",
        ),
    ],
)
async def test_verify_redirect_uri_metadata_loopback(
    hass: HomeAssistant,
    mock_session: AiohttpClientMocker,
    client_id: str,
    registered_uri: str,
    redirect_uri: str,
) -> None:
    """Allow native clients to choose the port of a registered loopback callback."""
    mock_session.get(
        client_id,
        json={"client_id": client_id, "redirect_uris": [registered_uri]},
    )

    assert not await indieauth.verify_redirect_uri(
        hass,
        client_id,
        redirect_uri,
        request_scheme=REQUEST_SCHEME,
        request_netloc=REQUEST_NETLOC,
    )
    assert await indieauth.verify_redirect_uri(
        hass,
        client_id,
        redirect_uri,
        allow_loopback_port_change=True,
        request_scheme=REQUEST_SCHEME,
        request_netloc=REQUEST_NETLOC,
    )


@pytest.mark.parametrize(
    ("registered_uri", "redirect_uri"),
    [
        pytest.param(
            "http://localhost/callback", "http://localhost:12345/other", id="path"
        ),
        pytest.param(
            "http://localhost/callback",
            "http://localhost:12345/callback?other=1",
            id="query",
        ),
        pytest.param(
            "http://localhost/callback",
            "http://localhost:12345/callback?",
            id="empty-query",
        ),
        pytest.param(
            "http://localhost/callback",
            "http://localhost:12345/callback#",
            id="fragment",
        ),
        pytest.param(
            "http://localhost/callback",
            "http://localhost:12345/call%62ack",
            id="encoding",
        ),
        pytest.param(
            "http://localhost/callback",
            "http://localhost:12345/call\nback",
            id="newline",
        ),
        pytest.param(
            "http://localhost/callback",
            " http://localhost:12345/callback",
            id="leading-space",
        ),
        pytest.param(
            "http://localhost/callback",
            "http://local\nhost:12345/callback",
            id="host-newline",
        ),
        pytest.param(
            "http://localhost/callback",
            "http://localhost:12345/Callback",
            id="path-case",
        ),
        pytest.param(
            "http://localhost/callback", "https://localhost:12345/callback", id="scheme"
        ),
        pytest.param(
            "http://localhost/callback",
            "HTTP://localhost:12345/callback",
            id="requested-scheme-case-differs",
        ),
        pytest.param(
            "HTTP://localhost/callback",
            "http://localhost:12345/callback",
            id="registered-scheme-case-differs",
        ),
        pytest.param(
            "http://localhost/callback",
            "http://127.0.0.1:12345/callback",
            id="different-loopback-host",
        ),
        pytest.param(
            "http://localhost/callback",
            "http://localhost.example.com:12345/callback",
            id="hostname-suffix",
        ),
        pytest.param(
            "http://localhost/callback",
            "http://user@localhost:12345/callback",
            id="userinfo",
        ),
        pytest.param(
            "http://localhost/callback",
            "http://localhost:invalid/callback",
            id="invalid-port",
        ),
        pytest.param(
            "http://localhost/callback",
            "http://localhost:65536/callback",
            id="port-out-of-range",
        ),
        pytest.param(
            "http://localhost/callback", "http://localhost:0/callback", id="zero-port"
        ),
        pytest.param(
            "http://localhost/callback", "http://localhost:/callback", id="empty-port"
        ),
        pytest.param(
            "https://localhost/callback",
            "https://localhost:12345/callback",
            id="https-loopback",
        ),
        pytest.param(
            "http://192.168.1.1/callback",
            "http://192.168.1.1:12345/callback",
            id="private-ip",
        ),
        pytest.param(
            "http://other.com/callback",
            "http://other.com:12345/callback",
            id="remote-host",
        ),
        pytest.param(
            "http://[::1]/callback",
            "http://[::2]:12345/callback",
            id="non-loopback-ipv6",
        ),
    ],
)
async def test_verify_redirect_uri_metadata_loopback_rejected(
    hass: HomeAssistant,
    mock_session: AiohttpClientMocker,
    registered_uri: str,
    redirect_uri: str,
) -> None:
    """Only the port of an HTTP loopback callback may differ."""
    client_id = "https://example.com/client"
    mock_session.get(
        client_id,
        json={"client_id": client_id, "redirect_uris": [registered_uri]},
    )

    assert not await indieauth.verify_redirect_uri(
        hass,
        client_id,
        redirect_uri,
        allow_loopback_port_change=True,
        request_scheme=REQUEST_SCHEME,
        request_netloc=REQUEST_NETLOC,
    )


async def test_fetch_redirect_uris_metadata_document_invalid_utf8(
    hass: HomeAssistant, mock_session: AiohttpClientMocker
) -> None:
    """Test a metadata document with invalid UTF-8 is rejected."""
    mock_session.get(
        "https://example.com/client",
        content=(
            b'{"client_id": "https://example.com/client",'
            b' "redirect_uris": ["https://other.com/callback"], "note": "\xff"}'
        ),
        headers={"Content-Type": "application/json"},
    )

    assert await indieauth.fetch_redirect_uris(hass, "https://example.com/client") == []


@pytest.mark.parametrize(
    "client_id",
    [
        pytest.param("https://example.com", id="no-path"),
        pytest.param("https://example.com/client#", id="empty-fragment"),
    ],
)
async def test_fetch_redirect_uris_metadata_document_invalid_client_id(
    hass: HomeAssistant, mock_session: AiohttpClientMocker, client_id: str
) -> None:
    """Test client ids violating the metadata document URL rules are ignored."""
    mock_session.get(
        client_id,
        text=json.dumps(
            {
                "client_id": client_id,
                "redirect_uris": ["https://other.com/callback"],
            }
        ),
        headers={"Content-Type": "application/json"},
    )

    assert await indieauth.fetch_redirect_uris(hass, client_id) == []


async def test_fetch_redirect_uris_metadata_document_not_ok(
    hass: HomeAssistant, mock_session: AiohttpClientMocker
) -> None:
    """Test a metadata document not served with 200 OK is ignored."""
    mock_session.get(
        "https://example.com/client",
        text=json.dumps(
            {
                "client_id": "https://example.com/client",
                "redirect_uris": ["https://example.com/callback"],
            }
        ),
        status=404,
        headers={"Content-Type": "application/json"},
    )

    assert await indieauth.fetch_redirect_uris(hass, "https://example.com/client") == []


async def test_fetch_redirect_uris_metadata_document_http_scheme(
    hass: HomeAssistant, mock_session: AiohttpClientMocker
) -> None:
    """Test a metadata document served over http is ignored."""
    client_id = "http://example.com/client"
    mock_session.get(
        client_id,
        text=json.dumps(
            {
                "client_id": client_id,
                "redirect_uris": ["https://other.com/callback"],
            }
        ),
        headers={"Content-Type": "application/json"},
    )

    assert await indieauth.fetch_redirect_uris(hass, client_id) == []
    assert not await indieauth.verify_redirect_uri(
        hass,
        client_id,
        "https://other.com/callback",
        request_scheme=REQUEST_SCHEME,
        request_netloc=REQUEST_NETLOC,
    )


async def test_fetch_redirect_uris_metadata_document_redirected(
    hass: HomeAssistant, mock_session: AiohttpClientMocker
) -> None:
    """Test a metadata document reached via a redirect is ignored."""
    mock_session.get(
        "https://example.com/client",
        text=json.dumps(
            {
                "client_id": "https://example.com/client",
                "redirect_uris": ["https://example.com/callback"],
            }
        ),
        headers={"Content-Type": "application/json"},
        history=(object(),),
    )

    assert await indieauth.fetch_redirect_uris(hass, "https://example.com/client") == []


async def test_fetch_redirect_uris_metadata_document_private_use_scheme(
    hass: HomeAssistant, mock_session: AiohttpClientMocker
) -> None:
    """Test a private-use scheme redirect uri is accepted as an absolute URI."""
    mock_session.get(
        "https://example.com/client",
        text=json.dumps(
            {
                "client_id": "https://example.com/client",
                "redirect_uris": ["app:/oauth-callback"],
            }
        ),
        headers={"Content-Type": "application/json"},
    )

    assert await indieauth.fetch_redirect_uris(hass, "https://example.com/client") == [
        "app:/oauth-callback"
    ]


async def test_fetch_redirect_uris_metadata_document_oversized(
    hass: HomeAssistant, mock_session: AiohttpClientMocker
) -> None:
    """Test a document past the 10kB cap is rejected as an incomplete read."""
    mock_session.get(
        "https://example.com/client",
        text=json.dumps(
            {
                "client_id": "https://example.com/client",
                "redirect_uris": ["https://example.com/callback"],
                "padding": "x" * 11000,
            }
        ),
        headers={"Content-Type": "application/json"},
    )

    assert await indieauth.fetch_redirect_uris(hass, "https://example.com/client") == []


async def test_fetch_redirect_uris_metadata_document_exactly_at_cap(
    hass: HomeAssistant, mock_session: AiohttpClientMocker
) -> None:
    """Test a document of exactly the read cap is rejected as possibly truncated."""
    document = {
        "client_id": "https://example.com/client",
        "redirect_uris": ["https://other.com/callback"],
        "padding": "",
    }
    document["padding"] = "x" * (10240 - len(json.dumps(document)))
    text = json.dumps(document)
    assert len(text) == 10240

    mock_session.get(
        "https://example.com/client",
        text=text,
        headers={"Content-Type": "application/json"},
    )

    assert await indieauth.fetch_redirect_uris(hass, "https://example.com/client") == []


async def test_fetch_redirect_uris_metadata_document_at_cap_ineligible(
    hass: HomeAssistant, mock_session: AiohttpClientMocker
) -> None:
    """Test a valid document that reaches the 10kB cap is ineligible."""
    mock_session.get(
        "https://example.com/client",
        text=json.dumps(
            {
                "client_id": "https://example.com/client",
                "redirect_uris": [
                    f"https://example.com/callback/{index}" for index in range(400)
                ],
            }
        ),
        headers={"Content-Type": "application/json"},
    )

    assert await indieauth.fetch_redirect_uris(hass, "https://example.com/client") == []


async def test_fetch_redirect_uris_network_error(
    hass: HomeAssistant, mock_session: AiohttpClientMocker
) -> None:
    """Test a network error yields no redirect uris without raising."""
    mock_session.get("https://example.com/client", exc=aiohttp.ClientError())

    assert await indieauth.fetch_redirect_uris(hass, "https://example.com/client") == []


@pytest.mark.parametrize(
    "client_id",
    ["https://home-assistant.io/android", "https://home-assistant.io/iOS"],
)
async def test_verify_redirect_uri_android_ios(client_id) -> None:
    """Test that we verify redirect uri correctly for Android/iOS."""
    with patch.object(indieauth, "fetch_redirect_uris", return_value=[]):
        assert await indieauth.verify_redirect_uri(
            None,
            client_id,
            "homeassistant://auth-callback",
            request_scheme=REQUEST_SCHEME,
            request_netloc=REQUEST_NETLOC,
        )

        assert not await indieauth.verify_redirect_uri(
            None,
            client_id,
            "homeassistant://something-else",
            request_scheme=REQUEST_SCHEME,
            request_netloc=REQUEST_NETLOC,
        )

        assert not await indieauth.verify_redirect_uri(
            None,
            "https://incorrect.com",
            "homeassistant://auth-callback",
            request_scheme=REQUEST_SCHEME,
            request_netloc=REQUEST_NETLOC,
        )

        if client_id == "https://home-assistant.io/android":
            assert await indieauth.verify_redirect_uri(
                None,
                client_id,
                "https://wear.googleapis.com/3p_auth/io.homeassistant.companion.android",
                request_scheme=REQUEST_SCHEME,
                request_netloc=REQUEST_NETLOC,
            )
            assert await indieauth.verify_redirect_uri(
                None,
                client_id,
                "https://wear.googleapis-cn.com/3p_auth/io.homeassistant.companion.android",
                request_scheme=REQUEST_SCHEME,
                request_netloc=REQUEST_NETLOC,
            )
        else:
            assert not await indieauth.verify_redirect_uri(
                None,
                client_id,
                "https://wear.googleapis.com/3p_auth/io.homeassistant.companion.android",
                request_scheme=REQUEST_SCHEME,
                request_netloc=REQUEST_NETLOC,
            )
            assert not await indieauth.verify_redirect_uri(
                None,
                client_id,
                "https://wear.googleapis-cn.com/3p_auth/io.homeassistant.companion.android",
                request_scheme=REQUEST_SCHEME,
                request_netloc=REQUEST_NETLOC,
            )
