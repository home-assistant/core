"""Tests for the client validator."""

import asyncio
from unittest.mock import patch

import pytest

from homeassistant.components.auth import indieauth
from homeassistant.core import HomeAssistant

from tests.test_util.aiohttp import AiohttpClientMocker


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
    assert indieauth._parse_client_id("http://ex.com/")
    assert indieauth._parse_client_id("https://ex.com/")

    with pytest.raises(ValueError):
        indieauth._parse_client_id("ftp://ex.com")


def test_client_id_path() -> None:
    """Test we enforce valid path."""
    assert indieauth._parse_client_id("http://ex.com").path == "/"
    assert indieauth._parse_client_id("http://ex.com/hello").path == "/hello"
    assert (
        indieauth._parse_client_id("http://ex.com/hello/.world").path == "/hello/.world"
    )
    assert (
        indieauth._parse_client_id("http://ex.com/hello./.world").path
        == "/hello./.world"
    )

    with pytest.raises(ValueError):
        indieauth._parse_client_id("http://ex.com/.")

    with pytest.raises(ValueError):
        indieauth._parse_client_id("http://ex.com/hello/./yo")

    with pytest.raises(ValueError):
        indieauth._parse_client_id("http://ex.com/hello/../yo")


def test_client_id_fragment() -> None:
    """Test we enforce valid fragment."""
    with pytest.raises(ValueError):
        indieauth._parse_client_id("http://ex.com/#yoo")


def test_client_id_user_pass() -> None:
    """Test we enforce valid username/password."""
    with pytest.raises(ValueError):
        indieauth._parse_client_id("http://user@ex.com/")

    with pytest.raises(ValueError):
        indieauth._parse_client_id("http://user:pass@ex.com/")


def test_client_id_hostname() -> None:
    """Test we enforce valid hostname."""
    assert indieauth._parse_client_id("http://www.home-assistant.io/")
    assert indieauth._parse_client_id("http://[::1]")
    assert indieauth._parse_client_id("http://127.0.0.1")
    assert indieauth._parse_client_id("http://10.0.0.0")
    assert indieauth._parse_client_id("http://10.255.255.255")
    assert indieauth._parse_client_id("http://172.16.0.0")
    assert indieauth._parse_client_id("http://172.31.255.255")
    assert indieauth._parse_client_id("http://192.168.0.0")
    assert indieauth._parse_client_id("http://192.168.255.255")

    with pytest.raises(ValueError):
        assert indieauth._parse_client_id("http://255.255.255.255/")
    with pytest.raises(ValueError):
        assert indieauth._parse_client_id("http://11.0.0.0/")
    with pytest.raises(ValueError):
        assert indieauth._parse_client_id("http://172.32.0.0/")
    with pytest.raises(ValueError):
        assert indieauth._parse_client_id("http://192.167.0.0/")


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
        None, "http://ex.com", "http://ex.com/callback"
    )

    with patch.object(indieauth, "fetch_redirect_uris", return_value=[]):
        # Different domain
        assert not await indieauth.verify_redirect_uri(
            None, "http://ex.com", "http://different.com/callback"
        )

        # Different scheme
        assert not await indieauth.verify_redirect_uri(
            None, "http://ex.com", "https://ex.com/callback"
        )

        # Different subdomain
        assert not await indieauth.verify_redirect_uri(
            None, "https://sub1.ex.com", "https://sub2.ex.com/callback"
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


@pytest.mark.parametrize(
    "client_id",
    ["https://home-assistant.io/android", "https://home-assistant.io/iOS"],
)
async def test_verify_redirect_uri_android_ios(client_id) -> None:
    """Test that we verify redirect uri correctly for Android/iOS."""
    with patch.object(indieauth, "fetch_redirect_uris", return_value=[]):
        assert await indieauth.verify_redirect_uri(
            None, client_id, "homeassistant://auth-callback"
        )

        assert not await indieauth.verify_redirect_uri(
            None, client_id, "homeassistant://something-else"
        )

        assert not await indieauth.verify_redirect_uri(
            None, "https://incorrect.com", "homeassistant://auth-callback"
        )

        if client_id == "https://home-assistant.io/android":
            assert await indieauth.verify_redirect_uri(
                None,
                client_id,
                "https://wear.googleapis.com/3p_auth/io.homeassistant.companion.android",
            )
            assert await indieauth.verify_redirect_uri(
                None,
                client_id,
                "https://wear.googleapis-cn.com/3p_auth/io.homeassistant.companion.android",
            )
        else:
            assert not await indieauth.verify_redirect_uri(
                None,
                client_id,
                "https://wear.googleapis.com/3p_auth/io.homeassistant.companion.android",
            )
            assert not await indieauth.verify_redirect_uri(
                None,
                client_id,
                "https://wear.googleapis-cn.com/3p_auth/io.homeassistant.companion.android",
            )
