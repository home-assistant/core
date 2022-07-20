"""Tests for the Cast integration helpers."""
import asyncio

from aiohttp import client_exceptions
import pytest

from homeassistant.components.cast.helpers import (
    PlaylistError,
    PlaylistItem,
    PlaylistSupported,
    parse_playlist,
)

from tests.common import load_fixture


@pytest.mark.parametrize(
    "url,fixture,content_type",
    (
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
    ),
)
async def test_hls_playlist_supported(hass, aioclient_mock, url, fixture, content_type):
    """Test playlist parsing of HLS playlist."""
    headers = {"content-type": content_type}
    aioclient_mock.get(url, text=load_fixture(fixture, "cast"), headers=headers)
    with pytest.raises(PlaylistSupported):
        await parse_playlist(hass, url)


@pytest.mark.parametrize(
    "url,fixture,content_type,expected_playlist",
    (
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
    ),
)
async def test_parse_playlist(
    hass, aioclient_mock, url, fixture, content_type, expected_playlist
):
    """Test playlist parsing of HLS playlist."""
    headers = {"content-type": content_type}
    aioclient_mock.get(url, text=load_fixture(fixture, "cast"), headers=headers)
    playlist = await parse_playlist(hass, url)
    assert expected_playlist == playlist


@pytest.mark.parametrize(
    "url,fixture",
    (
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
    ),
)
async def test_parse_bad_playlist(hass, aioclient_mock, url, fixture):
    """Test playlist parsing of HLS playlist."""
    aioclient_mock.get(url, text=load_fixture(fixture, "cast"))
    with pytest.raises(PlaylistError):
        await parse_playlist(hass, url)


@pytest.mark.parametrize(
    "url,exc",
    (
        ("http://sverigesradio.se/164-hi-aac.pls", asyncio.TimeoutError),
        ("http://sverigesradio.se/164-hi-aac.pls", client_exceptions.ClientError),
    ),
)
async def test_parse_http_error(hass, aioclient_mock, url, exc):
    """Test playlist parsing of HLS playlist when aioclient raises."""
    aioclient_mock.get(url, text="", exc=exc)
    with pytest.raises(PlaylistError):
        await parse_playlist(hass, url)
