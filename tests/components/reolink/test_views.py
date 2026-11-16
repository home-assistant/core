"""Tests for the Reolink views platform."""

import asyncio
from collections.abc import AsyncGenerator
from datetime import datetime, timedelta
from http import HTTPStatus
from typing import Any, cast
from unittest.mock import AsyncMock, MagicMock, patch

from aiohttp import ClientResponse
import pytest
from pytest_homeassistant.common import MockConfigEntry, async_fire_time_changed
from pytest_homeassistant.typing import ClientSessionGenerator
from reolink_aio.baichuan.media_decoder import HLS_INIT, HLS_PLAYLIST
from reolink_aio.exceptions import ReolinkError, UnexpectedDataError

from homeassistant.components.reolink.hls import IDLE_TIMEOUT, ReolinkHlsPlayback
from homeassistant.components.reolink.util import get_host
from homeassistant.components.reolink.views import (
    MAX_PARALLEL_THUMBNAILS,
    async_generate_playback_proxy_url,
    async_generate_thumbnail_url,
)
from homeassistant.core import HomeAssistant
from homeassistant.util import dt as dt_util

TEST_STREAM = "sub"
TEST_CHANNEL = "0"
TEST_ERROR = "TestError"
TEST_HLS_START = datetime(2023, 11, 14, 13, 12, 0)
TEST_HLS_END = datetime(2023, 11, 14, 13, 17, 0)
TEST_HLS_SEGMENT = "0.m4s"
TEST_TIME_ID = "20231114131200"
TEST_IMAGE = b"jpeg"


async def start_hls_playback(
    hass: HomeAssistant,
    reolink_host: MagicMock,
    config_entry: MockConfigEntry,
    stream_hls: Any,
) -> tuple[ReolinkHlsPlayback, str]:
    """Set up the config entry and start a HLS playback.

    Returns the playback and the URL of its playlist.
    """
    reolink_host.baichuan.stream_hls = MagicMock(side_effect=stream_hls)

    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    playback = await config_entry.runtime_data.host.async_start_hls_playback(
        int(TEST_CHANNEL), TEST_STREAM, TEST_HLS_START, TEST_HLS_END
    )
    return playback, async_generate_playback_proxy_url(
        config_entry.entry_id, playback.token
    )


async def test_hls_playback(
    hass: HomeAssistant,
    reolink_host: MagicMock,
    config_entry: MockConfigEntry,
    hass_client_no_auth: ClientSessionGenerator,
) -> None:
    """Test serving the HLS files of a recording."""

    async def stream_hls(*args: Any) -> AsyncGenerator[tuple[str, bytes]]:
        yield HLS_PLAYLIST, b"playlist"
        yield HLS_INIT, b"init"
        yield TEST_HLS_SEGMENT, b"segment"

    _, playlist_url = await start_hls_playback(
        hass, reolink_host, config_entry, stream_hls
    )
    reolink_host.baichuan.stream_hls.assert_called_once_with(
        int(TEST_CHANNEL), TEST_HLS_START, TEST_HLS_END, TEST_STREAM, "ffmpeg"
    )

    http_client = await hass_client_no_auth()
    response = cast(ClientResponse, await http_client.get(playlist_url))
    assert response.status == HTTPStatus.OK
    assert response.content_type == "application/vnd.apple.mpegurl"
    assert await response.read() == b"playlist"

    for filename, content in ((HLS_INIT, b"init"), (TEST_HLS_SEGMENT, b"segment")):
        url = playlist_url.replace(HLS_PLAYLIST, filename)
        response = cast(ClientResponse, await http_client.get(url))
        assert response.status == HTTPStatus.OK
        assert response.content_type == "video/mp4"
        assert await response.read() == content

    # a file that is not part of the finished download
    url = playlist_url.replace(HLS_PLAYLIST, "1.m4s")
    response = cast(ClientResponse, await http_client.get(url))
    assert response.status == HTTPStatus.NOT_FOUND


async def test_hls_playback_wait_for_download(
    hass: HomeAssistant,
    reolink_host: MagicMock,
    config_entry: MockConfigEntry,
    hass_client_no_auth: ClientSessionGenerator,
) -> None:
    """Test a request for a HLS file waits until the file is downloaded."""
    downloaded = asyncio.Event()

    async def stream_hls(*args: Any) -> AsyncGenerator[tuple[str, bytes]]:
        yield HLS_PLAYLIST, b"playlist"
        await downloaded.wait()
        yield TEST_HLS_SEGMENT, b"segment"

    _, playlist_url = await start_hls_playback(
        hass, reolink_host, config_entry, stream_hls
    )

    http_client = await hass_client_no_auth()
    url = playlist_url.replace(HLS_PLAYLIST, TEST_HLS_SEGMENT)
    request = hass.async_create_task(http_client.get(url))
    await asyncio.sleep(0.1)
    assert not request.done()

    downloaded.set()
    response = cast(ClientResponse, await request)
    assert response.status == HTTPStatus.OK
    assert await response.read() == b"segment"


async def test_hls_playback_timeout(
    hass: HomeAssistant,
    reolink_host: MagicMock,
    config_entry: MockConfigEntry,
    hass_client_no_auth: ClientSessionGenerator,
) -> None:
    """Test a request for a HLS file which is not downloaded in time."""

    async def stream_hls(*args: Any) -> AsyncGenerator[tuple[str, bytes]]:
        yield HLS_PLAYLIST, b"playlist"
        await asyncio.Event().wait()

    _, playlist_url = await start_hls_playback(
        hass, reolink_host, config_entry, stream_hls
    )

    http_client = await hass_client_no_auth()
    url = playlist_url.replace(HLS_PLAYLIST, TEST_HLS_SEGMENT)
    with patch("homeassistant.components.reolink.hls.FILE_TIMEOUT", 0):
        response = cast(ClientResponse, await http_client.get(url))
    assert response.status == HTTPStatus.NOT_FOUND


async def test_hls_playback_download_error(
    hass: HomeAssistant,
    reolink_host: MagicMock,
    config_entry: MockConfigEntry,
    hass_client_no_auth: ClientSessionGenerator,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test an error while downloading the recording."""

    async def stream_hls(*args: Any) -> AsyncGenerator[tuple[str, bytes]]:
        yield HLS_PLAYLIST, b"playlist"
        raise UnexpectedDataError(TEST_ERROR)

    _, playlist_url = await start_hls_playback(
        hass, reolink_host, config_entry, stream_hls
    )

    http_client = await hass_client_no_auth()
    url = playlist_url.replace(HLS_PLAYLIST, TEST_HLS_SEGMENT)
    response = cast(ClientResponse, await http_client.get(url))
    assert response.status == HTTPStatus.NOT_FOUND
    assert "Reolink playback error while downloading" in caplog.text


async def test_hls_playback_invalid_url(
    hass: HomeAssistant,
    reolink_host: MagicMock,
    config_entry: MockConfigEntry,
    hass_client_no_auth: ClientSessionGenerator,
) -> None:
    """Test the HLS view with a wrong token or config entry id."""

    async def stream_hls(*args: Any) -> AsyncGenerator[tuple[str, bytes]]:
        yield HLS_PLAYLIST, b"playlist"

    playback, _ = await start_hls_playback(hass, reolink_host, config_entry, stream_hls)

    http_client = await hass_client_no_auth()
    for url in (
        async_generate_playback_proxy_url(config_entry.entry_id, "wrong_token"),
        async_generate_playback_proxy_url("wrong_config_entry_id", playback.token),
    ):
        response = cast(ClientResponse, await http_client.get(url))
        assert response.status == HTTPStatus.NOT_FOUND


async def test_hls_playback_stop_previous(
    hass: HomeAssistant,
    reolink_host: MagicMock,
    config_entry: MockConfigEntry,
    hass_client_no_auth: ClientSessionGenerator,
) -> None:
    """Test a new HLS playback stops the previous one.

    A Reolink device allows only one download at a time.
    """
    first_closed = asyncio.Event()

    async def first_stream() -> AsyncGenerator[tuple[str, bytes]]:
        try:
            yield HLS_PLAYLIST, b"first"
            await asyncio.Event().wait()
        finally:
            first_closed.set()

    async def second_stream() -> AsyncGenerator[tuple[str, bytes]]:
        yield HLS_PLAYLIST, b"second"

    _, first_url = await start_hls_playback(
        hass, reolink_host, config_entry, [first_stream(), second_stream()]
    )

    http_client = await hass_client_no_auth()
    response = cast(ClientResponse, await http_client.get(first_url))
    assert await response.read() == b"first"
    assert not first_closed.is_set()

    host = config_entry.runtime_data.host
    second = await host.async_start_hls_playback(
        int(TEST_CHANNEL), TEST_STREAM, TEST_HLS_START, TEST_HLS_END
    )
    assert first_closed.is_set()

    response = cast(ClientResponse, await http_client.get(first_url))
    assert response.status == HTTPStatus.NOT_FOUND

    second_url = async_generate_playback_proxy_url(config_entry.entry_id, second.token)
    response = cast(ClientResponse, await http_client.get(second_url))
    assert await response.read() == b"second"


async def test_hls_playback_idle(
    hass: HomeAssistant,
    reolink_host: MagicMock,
    config_entry: MockConfigEntry,
    hass_client_no_auth: ClientSessionGenerator,
) -> None:
    """Test the downloaded HLS files are removed when no longer requested."""

    async def stream_hls(*args: Any) -> AsyncGenerator[tuple[str, bytes]]:
        yield HLS_PLAYLIST, b"playlist"

    _, playlist_url = await start_hls_playback(
        hass, reolink_host, config_entry, stream_hls
    )

    http_client = await hass_client_no_auth()
    response = cast(ClientResponse, await http_client.get(playlist_url))
    assert response.status == HTTPStatus.OK

    async_fire_time_changed(hass, dt_util.utcnow() + timedelta(seconds=IDLE_TIMEOUT))
    await hass.async_block_till_done()

    response = cast(ClientResponse, await http_client.get(playlist_url))
    assert response.status == HTTPStatus.NOT_FOUND


@pytest.mark.parametrize(
    ("stream", "thumbnail_stream"),
    [
        ("sub", "sub"),
        ("main", "sub"),
        ("autotrack_sub", "telephoto_sub"),
        ("autotrack_main", "telephoto_sub"),
        ("telephoto_sub", "telephoto_sub"),
        ("telephoto_main", "telephoto_sub"),
    ],
)
async def test_thumbnail(
    hass: HomeAssistant,
    reolink_host: MagicMock,
    config_entry: MockConfigEntry,
    hass_client: ClientSessionGenerator,
    stream: str,
    thumbnail_stream: str,
) -> None:
    """Test getting the thumbnail of a recording."""
    reolink_host.baichuan.snapshot_past = AsyncMock(return_value=TEST_IMAGE)

    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    thumbnail_url = async_generate_thumbnail_url(
        config_entry.entry_id, int(TEST_CHANNEL), stream, TEST_TIME_ID
    )

    http_client = await hass_client()
    response = await http_client.get(thumbnail_url)

    assert response.status == 200
    assert response.content_type == "image/jpeg"
    assert await response.content.read() == TEST_IMAGE
    reolink_host.baichuan.snapshot_past.assert_called_once()
    args = reolink_host.baichuan.snapshot_past.call_args.args
    assert args[0] == int(TEST_CHANNEL)
    assert args[1] == datetime(2023, 11, 14, 13, 12, 0)
    assert args[2] == thumbnail_stream


@pytest.mark.parametrize(
    ("stream", "thumbnail_stream"),
    [
        ("main", "main"),
        ("autotrack_main", "telephoto_main"),
        ("telephoto_main", "telephoto_main"),
    ],
)
async def test_thumbnail_no_sub_stream(
    hass: HomeAssistant,
    reolink_host: MagicMock,
    config_entry: MockConfigEntry,
    hass_client: ClientSessionGenerator,
    stream: str,
    thumbnail_stream: str,
) -> None:
    """Test the thumbnail of a camera without a sub stream uses the main stream."""
    reolink_host.baichuan.snapshot_past = AsyncMock(return_value=TEST_IMAGE)

    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    reolink_host.supported.side_effect = lambda ch, key: key != "sub"

    http_client = await hass_client()
    response = await http_client.get(
        async_generate_thumbnail_url(
            config_entry.entry_id, int(TEST_CHANNEL), stream, TEST_TIME_ID
        )
    )

    assert response.status == 200
    assert await response.content.read() == TEST_IMAGE
    assert reolink_host.baichuan.snapshot_past.call_args.args[2] == thumbnail_stream


@pytest.mark.parametrize(
    (
        "config_entry_id",
        "channel",
        "stream",
        "time_id",
        "side_effect",
        "body",
    ),
    [
        pytest.param(
            "wrong_config_id",
            TEST_CHANNEL,
            TEST_STREAM,
            TEST_TIME_ID,
            None,
            "Reolink thumbnail could not find config entry id: wrong_config_id",
            id="unknown_config_entry",
        ),
        pytest.param(
            None,
            "abc",
            TEST_STREAM,
            TEST_TIME_ID,
            None,
            f"Reolink thumbnail invalid channel abc or time {TEST_TIME_ID}",
            id="invalid_channel",
        ),
        pytest.param(
            None,
            TEST_CHANNEL,
            TEST_STREAM,
            "invalid",
            None,
            f"Reolink thumbnail invalid channel {TEST_CHANNEL} or time invalid",
            id="invalid_time",
        ),
        pytest.param(
            None,
            TEST_CHANNEL,
            "main",
            TEST_TIME_ID,
            None,
            "Reolink thumbnail invalid stream main",
            id="invalid_stream",
        ),
        pytest.param(
            None,
            TEST_CHANNEL,
            TEST_STREAM,
            TEST_TIME_ID,
            ReolinkError(TEST_ERROR),
            TEST_ERROR,
            id="camera_error",
        ),
    ],
)
async def test_thumbnail_errors(
    hass: HomeAssistant,
    reolink_host: MagicMock,
    config_entry: MockConfigEntry,
    hass_client: ClientSessionGenerator,
    config_entry_id: str | None,
    channel: str,
    stream: str,
    time_id: str,
    side_effect: Exception | None,
    body: str,
) -> None:
    """Test errors while getting the thumbnail of a recording."""
    reolink_host.baichuan.snapshot_past = AsyncMock(
        return_value=TEST_IMAGE, side_effect=side_effect
    )

    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    http_client = await hass_client()
    response = await http_client.get(
        f"/api/reolink/thumbnail/{config_entry_id or config_entry.entry_id}"
        f"/{channel}/{stream}/{time_id}"
    )

    assert response.status == HTTPStatus.BAD_REQUEST
    assert await response.content.read() == bytes(body, "utf-8")


async def test_thumbnail_unloaded_config_entry(
    hass: HomeAssistant,
    reolink_host: MagicMock,
    config_entry: MockConfigEntry,
    hass_client: ClientSessionGenerator,
) -> None:
    """Test getting a thumbnail after the config entry has been unloaded."""
    reolink_host.baichuan.snapshot_past = AsyncMock(return_value=TEST_IMAGE)

    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()
    assert await hass.config_entries.async_unload(config_entry.entry_id)
    await hass.async_block_till_done()

    http_client = await hass_client()
    response = await http_client.get(
        async_generate_thumbnail_url(
            config_entry.entry_id, int(TEST_CHANNEL), TEST_STREAM, TEST_TIME_ID
        )
    )

    assert response.status == HTTPStatus.BAD_REQUEST
    reolink_host.baichuan.snapshot_past.assert_not_called()


async def test_thumbnail_unloaded_while_queued(
    hass: HomeAssistant,
    reolink_host: MagicMock,
    config_entry: MockConfigEntry,
    hass_client: ClientSessionGenerator,
) -> None:
    """Test a queued thumbnail request after the config entry has been unloaded."""
    release = asyncio.Event()

    async def snapshot_past(*args: Any) -> bytes:
        await release.wait()
        return TEST_IMAGE

    reolink_host.baichuan.snapshot_past = AsyncMock(side_effect=snapshot_past)

    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    http_client = await hass_client()
    thumbnail_url = async_generate_thumbnail_url(
        config_entry.entry_id, int(TEST_CHANNEL), TEST_STREAM, TEST_TIME_ID
    )
    with patch(
        "homeassistant.components.reolink.views.get_host", wraps=get_host
    ) as mock_get_host:
        requests = [
            asyncio.create_task(http_client.get(thumbnail_url))
            for _ in range(MAX_PARALLEL_THUMBNAILS)
        ]
        while reolink_host.baichuan.snapshot_past.call_count < MAX_PARALLEL_THUMBNAILS:
            await asyncio.sleep(0)
        checks = mock_get_host.call_count
        requests.append(asyncio.create_task(http_client.get(thumbnail_url)))
        # Past its first config entry check, the request waits for the semaphore.
        while mock_get_host.call_count == checks:
            await asyncio.sleep(0)

        assert await hass.config_entries.async_unload(config_entry.entry_id)
        release.set()
        responses = await asyncio.gather(*requests)

    assert sorted(response.status for response in responses) == [
        *[HTTPStatus.OK] * MAX_PARALLEL_THUMBNAILS,
        HTTPStatus.BAD_REQUEST,
    ]
    assert reolink_host.baichuan.snapshot_past.call_count == MAX_PARALLEL_THUMBNAILS
