"""Test media browser helpers for media player."""

from unittest.mock import Mock, patch

import pytest
from pytest_homeassistant.common import mock_component

from homeassistant.components.media_player.browse_media import (
    async_process_play_media_url,
)
from homeassistant.components.media_player.const import DOMAIN
from homeassistant.core import HomeAssistant
from homeassistant.core_config import async_process_ha_core_config
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.network import NoURLAvailableError


@pytest.fixture(name="mock_sign_path")
def fixture_mock_sign_path():
    """Mock sign path."""
    with patch(
        "homeassistant.components.media_player.browse_media.async_sign_path",
        side_effect=lambda _, url, _2: url + "?authSig=bla",
    ):
        yield


async def test_process_play_media_url(hass: HomeAssistant, mock_sign_path) -> None:
    """Test it prefixes and signs urls."""
    await async_process_ha_core_config(
        hass,
        {"internal_url": "http://example.local:8123"},
    )
    hass.config.api = Mock(use_ssl=False, port=8123, local_ip="192.168.123.123")

    # Not changing a url that is not a hass url
    assert (
        async_process_play_media_url(hass, "https://not-hass.com/path")
        == "https://not-hass.com/path"
    )
    # Not changing a url that is not http/https
    assert (
        async_process_play_media_url(hass, "file:///tmp/test.mp3")
        == "file:///tmp/test.mp3"
    )

    # Testing signing hass URLs
    assert (
        async_process_play_media_url(hass, "/path")
        == "http://example.local:8123/path?authSig=bla"
    )
    assert (
        async_process_play_media_url(hass, "http://example.local:8123/path")
        == "http://example.local:8123/path?authSig=bla"
    )
    assert (
        async_process_play_media_url(hass, "http://192.168.123.123:8123/path")
        == "http://192.168.123.123:8123/path?authSig=bla"
    )
    # Test skip signing URLs that have a query param
    assert (
        async_process_play_media_url(hass, "/path?hello=world")
        == "http://example.local:8123/path?hello=world"
    )
    assert (
        async_process_play_media_url(
            hass, "http://192.168.123.123:8123/path?hello=world"
        )
        == "http://192.168.123.123:8123/path?hello=world"
    )

    # Test skip signing URLs if they are known to require no auth
    assert (
        async_process_play_media_url(hass, "/api/tts_proxy/bla")
        == "http://example.local:8123/api/tts_proxy/bla"
    )
    assert (
        async_process_play_media_url(hass, "/local/bla")
        == "http://example.local:8123/local/bla"
    )
    assert (
        async_process_play_media_url(
            hass, "http://example.local:8123/api/tts_proxy/bla"
        )
        == "http://example.local:8123/api/tts_proxy/bla"
    )
    assert (
        async_process_play_media_url(
            hass, "http://example.local:8123/api/assist_satellite/static/bla"
        )
        == "http://example.local:8123/api/assist_satellite/static/bla"
    )

    # Not changing a URL which is not absolute and does not start with /
    assert async_process_play_media_url(hass, "hello") == "hello"


@pytest.mark.usefixtures("mock_sign_path")
@pytest.mark.parametrize(
    ("use_ssl", "translation_key"),
    [
        pytest.param(False, "no_url_available", id="no_ssl"),
        pytest.param(True, "no_url_available_configure_urls", id="ssl"),
    ],
)
async def test_process_play_media_url_no_url_available(
    hass: HomeAssistant, use_ssl: bool, translation_key: str
) -> None:
    """Test a translated error is raised when no URL is available."""
    hass.config.api = Mock(use_ssl=use_ssl, port=8123, local_ip="192.168.123.123")

    with (
        patch(
            "homeassistant.components.media_player.browse_media.get_url",
            side_effect=NoURLAvailableError,
        ),
        pytest.raises(HomeAssistantError) as exc_info,
    ):
        async_process_play_media_url(hass, "/path")

    assert exc_info.value.translation_domain == DOMAIN
    assert exc_info.value.translation_key == translation_key


async def test_process_play_media_url_for_addon(
    hass: HomeAssistant, mock_sign_path
) -> None:
    """Test it uses the hostname for an addon if available."""
    await async_process_ha_core_config(
        hass,
        {
            "internal_url": "http://example.local:8123",
            "external_url": "https://example.com",
        },
    )

    # Not hassio or hassio not loaded yet, don't use supervisor network url
    hass.config.api = Mock(use_ssl=False, port=8123, local_ip="192.168.123.123")
    assert (
        async_process_play_media_url(hass, "/path", for_supervisor_network=True)
        != "http://homeassistant:8123/path?authSig=bla"
    )

    # Is hassio and not SSL, use an supervisor network url
    mock_component(hass, "hassio")
    assert (
        async_process_play_media_url(hass, "/path", for_supervisor_network=True)
        == "http://homeassistant:8123/path?authSig=bla"
    )

    # Hassio loaded but using SSL, don't use an supervisor network url
    hass.config.api = Mock(use_ssl=True, port=8123, local_ip="192.168.123.123")
    assert (
        async_process_play_media_url(hass, "/path", for_supervisor_network=True)
        != "https://homeassistant:8123/path?authSig=bla"
    )
