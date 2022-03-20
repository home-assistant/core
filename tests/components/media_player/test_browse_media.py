"""Test media browser helpers for media player."""
from unittest.mock import Mock, patch

import pytest

from homeassistant.components.media_player.browse_media import (
    async_process_play_media_url,
)
from homeassistant.config import async_process_ha_core_config

from tests.common import mock_component


@pytest.fixture(name="mock_sign_path")
def fixture_mock_sign_path():
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


async def test_process_play_media_url_for_addon(hass, mock_sign_path):
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
