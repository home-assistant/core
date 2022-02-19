"""Test media browser helpers for media player."""
from unittest.mock import Mock, patch

import pytest

from homeassistant.components.media_player.browse_media import (
    async_process_play_media_url,
)
from homeassistant.config import async_process_ha_core_config


@pytest.fixture
def mock_sign_path():
    """Mock sign path."""
    with patch(
        "homeassistant.components.media_player.browse_media.async_sign_path",
        side_effect=lambda _, url, _2: url + "?authSig=bla",
    ):
        yield


async def test_process_play_media_url(hass, mock_sign_path):
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
