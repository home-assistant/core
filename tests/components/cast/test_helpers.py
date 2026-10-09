"""Tests for the Cast integration helpers."""

from threading import Thread
from unittest.mock import MagicMock, patch

from aiohttp import client_exceptions
import pytest

from homeassistant.components.cast import media_player as cast_media_player
from homeassistant.components.cast.const import DOMAIN
from homeassistant.components.cast.helpers import (
    CastStatusListener,
    PlaylistError,
    PlaylistItem,
    PlaylistSupported,
    parse_playlist,
)
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry, async_load_fixture
from tests.test_util.aiohttp import AiohttpClientMocker


@pytest.mark.parametrize(
    ("url", "fixture", "content_type"),
    [
        (
            "http://a.files.bbci.co.uk/media/live/manifesto/audio/simulcast/hls/nonuk/sbr_low/ak/bbc_radio_fourfm.m3u8",
            "bbc_radio_fourfm.m3u8",
            None,
        ),
        (
            "https://rthkaudio2-lh.akamaihd.net/i/radio2_1@355865/master.m3u8",
            "rthkaudio2.m3u8",
            "application/vnd.apple.mpegurl",
        ),
        (
            "https://rthkaudio2-lh.akamaihd.net/i/radio2_1@355865/master.m3u8",
            "rthkaudio2.m3u8",
            None,
        ),
    ],
)
async def test_hls_playlist_supported(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker, url, fixture, content_type
) -> None:
    """Test playlist parsing of HLS playlist."""
    headers = {"content-type": content_type}
    aioclient_mock.get(
        url, text=await async_load_fixture(hass, fixture, DOMAIN), headers=headers
    )
    with pytest.raises(PlaylistSupported):
        await parse_playlist(hass, url)


@pytest.mark.parametrize(
    ("url", "fixture", "content_type", "expected_playlist"),
    [
        (
            "https://sverigesradio.se/topsy/direkt/209-hi-mp3.m3u",
            "209-hi-mp3.m3u",
            "audio/x-mpegurl",
            [
                PlaylistItem(
                    length=["-1"],
                    title="Sveriges Radio",
                    url="https://http-live.sr.se/p4norrbotten-mp3-192",
                )
            ],
        ),
        (
            "https://sverigesradio.se/topsy/direkt/209-hi-mp3.m3u",
            "209-hi-mp3_bad_extinf.m3u",
            "audio/x-mpegurl",
            [
                PlaylistItem(
                    length=None,
                    title=None,
                    url="https://http-live.sr.se/p4norrbotten-mp3-192",
                )
            ],
        ),
        (
            "https://sverigesradio.se/topsy/direkt/209-hi-mp3.m3u",
            "209-hi-mp3_no_extinf.m3u",
            "audio/x-mpegurl",
            [
                PlaylistItem(
                    length=None,
                    title=None,
                    url="https://http-live.sr.se/p4norrbotten-mp3-192",
                )
            ],
        ),
        (
            "http://sverigesradio.se/topsy/direkt/164-hi-aac.pls",
            "164-hi-aac.pls",
            "audio/x-mpegurl",
            [
                PlaylistItem(
                    length="-1",
                    title="Sveriges Radio",
                    url="https://http-live.sr.se/p3-aac-192",
                )
            ],
        ),
    ],
)
async def test_parse_playlist(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
    url,
    fixture,
    content_type,
    expected_playlist,
) -> None:
    """Test playlist parsing of HLS playlist."""
    headers = {"content-type": content_type}
    aioclient_mock.get(
        url, text=await async_load_fixture(hass, fixture, DOMAIN), headers=headers
    )
    playlist = await parse_playlist(hass, url)
    assert expected_playlist == playlist


@pytest.mark.parametrize(
    ("url", "fixture"),
    [
        ("http://sverigesradio.se/164-hi-aac.pls", "164-hi-aac_invalid_entries.pls"),
        ("http://sverigesradio.se/164-hi-aac.pls", "164-hi-aac_invalid_file.pls"),
        ("http://sverigesradio.se/164-hi-aac.pls", "164-hi-aac_invalid_version.pls"),
        ("http://sverigesradio.se/164-hi-aac.pls", "164-hi-aac_invalid.pls"),
        ("http://sverigesradio.se/164-hi-aac.pls", "164-hi-aac_missing_file.pls"),
        ("http://sverigesradio.se/164-hi-aac.pls", "164-hi-aac_no_entries.pls"),
        ("http://sverigesradio.se/164-hi-aac.pls", "164-hi-aac_no_playlist.pls"),
        ("http://sverigesradio.se/164-hi-aac.pls", "164-hi-aac_no_version.pls"),
        ("https://sverigesradio.se/209-hi-mp3.m3u", "209-hi-mp3_bad_url.m3u"),
        ("https://sverigesradio.se/209-hi-mp3.m3u", "empty.m3u"),
    ],
)
async def test_parse_bad_playlist(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker, url, fixture
) -> None:
    """Test playlist parsing of HLS playlist."""
    aioclient_mock.get(url, text=await async_load_fixture(hass, fixture, DOMAIN))
    with pytest.raises(PlaylistError):
        await parse_playlist(hass, url)


@pytest.mark.parametrize(
    ("url", "exc"),
    [
        ("http://sverigesradio.se/164-hi-aac.pls", TimeoutError),
        ("http://sverigesradio.se/164-hi-aac.pls", client_exceptions.ClientError),
    ],
)
async def test_parse_http_error(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker, url, exc
) -> None:
    """Test playlist parsing of HLS playlist when aioclient raises."""
    aioclient_mock.get(url, text="", exc=exc)
    with pytest.raises(PlaylistError):
        await parse_playlist(hass, url)


async def test_stale_connection_status_listener(hass: HomeAssistant) -> None:
    """Test an old Cast listener cannot update a reconnected device."""
    entry = MockConfigEntry(domain=DOMAIN)
    info = MagicMock()
    info.uuid = MagicMock()
    info.is_audio_group = False
    info.friendly_name = "Test speaker"

    entity = cast_media_player.CastMediaPlayerEntity(hass, entry, info)
    entity.entity_id = "media_player.speaker"

    chromecast = MagicMock()
    chromecast.uuid = info.uuid
    mz_mgr = MagicMock()

    old_listener = CastStatusListener(entity, chromecast, mz_mgr)
    entity._status_listener = old_listener
    entity._chromecast = chromecast
    entity.mz_mgr = mz_mgr

    new_listener = CastStatusListener(entity, chromecast, mz_mgr)
    entity._status_listener = new_listener

    with patch.object(entity, "new_connection_status") as callback:
        old_listener.new_connection_status(MagicMock(status="CONNECTED"))
        new_listener.new_connection_status(MagicMock(status="CONNECTED"))

        # Allow the Home Assistant event loop to process scheduled callbacks.
        await hass.async_block_till_done()

        callback.assert_called_once()


async def test_connection_status_queued_before_invalidation(
    hass: HomeAssistant,
) -> None:
    """Test a queued connection callback is ignored after invalidation."""
    entry = MockConfigEntry(domain=DOMAIN)
    info = MagicMock()
    info.uuid = MagicMock()
    info.is_audio_group = False
    info.friendly_name = "Test speaker"

    entity = cast_media_player.CastMediaPlayerEntity(hass, entry, info)
    entity.entity_id = "media_player.speaker"

    chromecast = MagicMock()
    chromecast.uuid = info.uuid
    mz_mgr = MagicMock()

    listener = CastStatusListener(entity, chromecast, mz_mgr)
    entity._status_listener = listener
    entity._chromecast = chromecast
    entity.mz_mgr = mz_mgr

    with patch.object(entity, "new_connection_status") as callback:
        # Queue the callback without yielding to the event loop.
        thread = Thread(
            target=listener.new_connection_status,
            args=(MagicMock(status="CONNECTED"),),
        )
        thread.start()
        thread.join()

        # Invalidate the connection before the queued callback runs.
        entity._invalidate()

        await hass.async_block_till_done()

        callback.assert_not_called()
        assert entity._chromecast is None
        assert entity.mz_mgr is None
