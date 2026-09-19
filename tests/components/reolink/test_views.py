"""Tests for the Reolink views platform."""

from collections.abc import AsyncIterator
from http import HTTPStatus
import logging
import os
from pathlib import Path
from typing import Any, cast
from unittest.mock import AsyncMock, MagicMock, Mock, patch

from aiohttp import ClientConnectionError, ClientResponse
import pytest
from reolink_aio.enums import VodRequestType
from reolink_aio.exceptions import ReolinkError
from reolink_aio.typings import VOD_file_info

from homeassistant.components.reolink.views import (
    VOD_CACHE_MAX_BYTES,
    async_generate_playback_proxy_url,
)
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry
from tests.typing import ClientSessionGenerator

TEST_YEAR = 2023
TEST_MONTH = 11
TEST_DAY = 14
TEST_DAY2 = 15
TEST_HOUR = 13
TEST_MINUTE = 12
TEST_FILE_NAME_MP4 = (
    f"Mp4Record/{TEST_YEAR}-{TEST_MONTH}-{TEST_DAY}/RecS04_"
    f"{TEST_YEAR}{TEST_MONTH}{TEST_DAY}{TEST_HOUR}{TEST_MINUTE}"
    f"00_123456_AB123C.mp4"
)
TEST_TIME_RANGE = (
    f"{TEST_YEAR}{TEST_MONTH}{TEST_DAY}{TEST_HOUR}{TEST_MINUTE}00_"
    f"{TEST_YEAR}{TEST_MONTH}{TEST_DAY}{TEST_HOUR}{TEST_MINUTE}30"
)
TEST_STREAM = "sub"
TEST_CHANNEL = "0"
TEST_VOD_TYPE = VodRequestType.PLAYBACK.value
TEST_MIME_TYPE_MP4 = "video/mp4"
TEST_URL = "http://test_url&token=test"
TEST_ERROR = "TestError"


def get_mock_session(
    response: list[Any] | None = None,
    content_length: int = 8,
    content_type: str = TEST_MIME_TYPE_MP4,
) -> Mock:
    """Get a mock session to mock the camera response."""
    if response is None:
        response = [b"test", b"test", StopAsyncIteration()]

    content = Mock()
    content.__anext__ = AsyncMock(side_effect=response)
    content.__aiter__ = Mock(return_value=content)

    mock_response = Mock()
    mock_response.content_length = content_length
    mock_response.headers = {}
    mock_response.status = 200
    mock_response.reason = "OK"
    mock_response.content_type = content_type
    mock_response.content.iter_chunked = Mock(return_value=content)
    mock_response.text = AsyncMock(return_value="test")

    mock_session = Mock()
    mock_session.get = AsyncMock(return_value=mock_response)
    return mock_session


@pytest.mark.parametrize(
    ("content_type"),
    [("video/mp4"), ("application/octet-stream"), ("apolication/octet-stream")],
)
async def test_playback_proxy(
    hass: HomeAssistant,
    reolink_host: MagicMock,
    config_entry: MockConfigEntry,
    hass_client: ClientSessionGenerator,
    caplog: pytest.LogCaptureFixture,
    content_type: str,
) -> None:
    """Test successful playback proxy URL."""
    reolink_host.get_vod_source.return_value = (TEST_MIME_TYPE_MP4, TEST_URL)

    mock_session = get_mock_session(content_type=content_type)

    with patch(
        "homeassistant.components.reolink.views.async_get_clientsession",
        return_value=mock_session,
    ):
        assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()
    caplog.set_level(logging.DEBUG)

    proxy_url = async_generate_playback_proxy_url(
        config_entry.entry_id,
        TEST_CHANNEL,
        TEST_FILE_NAME_MP4,
        TEST_STREAM,
        TEST_VOD_TYPE,
    )

    http_client = await hass_client()
    response = cast(ClientResponse, await http_client.get(proxy_url))

    assert await response.content.read() == b"testtest"
    assert response.status == 200


async def test_proxy_get_source_error(
    hass: HomeAssistant,
    reolink_host: MagicMock,
    config_entry: MockConfigEntry,
    hass_client: ClientSessionGenerator,
) -> None:
    """Test error while getting source for playback proxy URL."""
    reolink_host.get_vod_source.side_effect = ReolinkError(TEST_ERROR)

    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    proxy_url = async_generate_playback_proxy_url(
        config_entry.entry_id,
        TEST_CHANNEL,
        TEST_FILE_NAME_MP4,
        TEST_STREAM,
        TEST_VOD_TYPE,
    )

    http_client = await hass_client()
    response = await http_client.get(proxy_url)

    assert await response.content.read() == bytes(TEST_ERROR, "utf-8")
    assert response.status == HTTPStatus.BAD_REQUEST


async def test_proxy_invalid_config_entry_id(
    hass: HomeAssistant,
    reolink_host: MagicMock,
    config_entry: MockConfigEntry,
    hass_client: ClientSessionGenerator,
) -> None:
    """Test config entry id not found for playback proxy URL."""
    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    proxy_url = async_generate_playback_proxy_url(
        "wrong_config_id",
        TEST_CHANNEL,
        TEST_FILE_NAME_MP4,
        TEST_STREAM,
        TEST_VOD_TYPE,
    )

    http_client = await hass_client()
    response = await http_client.get(proxy_url)

    assert await response.content.read() == bytes(
        "Reolink playback proxy could not find config entry id: wrong_config_id",
        "utf-8",
    )
    assert response.status == HTTPStatus.BAD_REQUEST


async def test_playback_proxy_timeout(
    hass: HomeAssistant,
    reolink_host: MagicMock,
    config_entry: MockConfigEntry,
    hass_client: ClientSessionGenerator,
) -> None:
    """Test playback proxy URL with a timeout in the second chunk."""
    reolink_host.get_vod_source.return_value = (TEST_MIME_TYPE_MP4, TEST_URL)

    mock_session = get_mock_session([b"test", TimeoutError()], 4)

    with patch(
        "homeassistant.components.reolink.views.async_get_clientsession",
        return_value=mock_session,
    ):
        assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    proxy_url = async_generate_playback_proxy_url(
        config_entry.entry_id,
        TEST_CHANNEL,
        TEST_FILE_NAME_MP4,
        TEST_STREAM,
        TEST_VOD_TYPE,
    )

    http_client = await hass_client()
    response = cast(ClientResponse, await http_client.get(proxy_url))

    assert await response.content.read() == b"test"
    assert response.status == 200


@pytest.mark.parametrize(("content_type"), [("video/x-flv"), ("text/html")])
async def test_playback_wrong_content(
    hass: HomeAssistant,
    reolink_host: MagicMock,
    config_entry: MockConfigEntry,
    hass_client: ClientSessionGenerator,
    content_type: str,
) -> None:
    """Test playback proxy URL with a wrong content type in the response."""
    reolink_host.get_vod_source.return_value = (TEST_MIME_TYPE_MP4, TEST_URL)

    mock_session = get_mock_session(content_type=content_type)

    with patch(
        "homeassistant.components.reolink.views.async_get_clientsession",
        return_value=mock_session,
    ):
        assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    proxy_url = async_generate_playback_proxy_url(
        config_entry.entry_id,
        TEST_CHANNEL,
        TEST_FILE_NAME_MP4,
        TEST_STREAM,
        TEST_VOD_TYPE,
    )

    http_client = await hass_client()
    response = cast(ClientResponse, await http_client.get(proxy_url))

    assert response.status == HTTPStatus.BAD_REQUEST


async def test_playback_connect_error(
    hass: HomeAssistant,
    reolink_host: MagicMock,
    config_entry: MockConfigEntry,
    hass_client: ClientSessionGenerator,
) -> None:
    """Test playback proxy URL with a connection error."""
    reolink_host.get_vod_source.return_value = (TEST_MIME_TYPE_MP4, TEST_URL)

    mock_session = Mock()
    mock_session.get = AsyncMock(side_effect=ClientConnectionError(TEST_ERROR))

    with patch(
        "homeassistant.components.reolink.views.async_get_clientsession",
        return_value=mock_session,
    ):
        assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    proxy_url = async_generate_playback_proxy_url(
        config_entry.entry_id,
        TEST_CHANNEL,
        TEST_FILE_NAME_MP4,
        TEST_STREAM,
        TEST_VOD_TYPE,
    )

    http_client = await hass_client()
    response = cast(ClientResponse, await http_client.get(proxy_url))

    assert response.status == HTTPStatus.BAD_REQUEST


TEST_VOD_DATA = b"0123456789" * 100


def mock_baichuan_vod(reolink_host: MagicMock, data: bytes = TEST_VOD_DATA) -> None:
    """Make the Baichuan VOD download hand back data."""
    reolink_host.baichuan.get_vod_file_info = AsyncMock(
        return_value=VOD_file_info(
            size=len(data),
            handle="0",
            file_id=TEST_FILE_NAME_MP4,
            resolved=True,
            file_type="h264",
            contains_audio=True,
        )
    )

    async def _download(
        channel: int, filename: str, **kwargs: Any
    ) -> AsyncIterator[bytes]:
        yield data

    reolink_host.baichuan.download_vod = Mock(side_effect=_download)


async def test_playback_proxy_baichuan(
    hass: HomeAssistant,
    reolink_host: MagicMock,
    config_entry: MockConfigEntry,
    hass_client: ClientSessionGenerator,
    tmp_path: Path,
) -> None:
    """Test the recording is served from the Baichuan download."""
    mock_baichuan_vod(reolink_host)

    with patch.object(hass.config, "cache_path", return_value=str(tmp_path)):
        assert await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()

        proxy_url = async_generate_playback_proxy_url(
            config_entry.entry_id,
            TEST_CHANNEL,
            TEST_FILE_NAME_MP4,
            TEST_STREAM,
            TEST_VOD_TYPE,
        )

        http_client = await hass_client()
        response = cast(ClientResponse, await http_client.get(proxy_url))

        assert response.status == 200
        assert response.headers["Content-Length"] == str(len(TEST_VOD_DATA))
        assert await response.content.read() == TEST_VOD_DATA

    reolink_host.get_vod_source.assert_not_called()


async def test_playback_proxy_baichuan_cache_expiry(
    hass: HomeAssistant,
    reolink_host: MagicMock,
    config_entry: MockConfigEntry,
    hass_client: ClientSessionGenerator,
    tmp_path: Path,
) -> None:
    """Test a recording is fetched again once its cached copy has aged out."""
    mock_baichuan_vod(reolink_host)

    with patch.object(hass.config, "cache_path", return_value=str(tmp_path)):
        assert await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()

        proxy_url = async_generate_playback_proxy_url(
            config_entry.entry_id,
            TEST_CHANNEL,
            TEST_FILE_NAME_MP4,
            TEST_STREAM,
            TEST_VOD_TYPE,
        )

        http_client = await hass_client()
        first = cast(ClientResponse, await http_client.get(proxy_url))
        assert first.status == 200
        await first.read()

        for cached in tmp_path.glob("*.mp4"):
            os.utime(cached, (0, 0))

        response = cast(ClientResponse, await http_client.get(proxy_url))

        assert response.status == 200
        assert await response.content.read() == TEST_VOD_DATA

    assert reolink_host.baichuan.download_vod.call_count == 2


async def test_playback_proxy_baichuan_skipped_for_nvr_download(
    hass: HomeAssistant,
    reolink_host: MagicMock,
    config_entry: MockConfigEntry,
    hass_client: ClientSessionGenerator,
) -> None:
    """Test an NVR download, which asks for a time range, never reaches Baichuan."""
    reolink_host.get_vod_source.return_value = (TEST_MIME_TYPE_MP4, TEST_URL)
    reolink_host.baichuan.get_vod_file_info = AsyncMock(
        side_effect=ReolinkError("Test error")
    )
    mock_session = get_mock_session(content_type="video/x-flv")

    with patch(
        "homeassistant.components.reolink.views.async_get_clientsession",
        return_value=mock_session,
    ):
        assert await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()
        http_client = await hass_client()

        # an flv answer to a playback request makes the view remember to ask for
        # a download from then on, which must not change what an NVR download is
        flv_url = async_generate_playback_proxy_url(
            config_entry.entry_id,
            TEST_CHANNEL,
            TEST_FILE_NAME_MP4,
            TEST_STREAM,
            TEST_VOD_TYPE,
        )
        flv_response = cast(ClientResponse, await http_client.get(flv_url))
        assert flv_response.status == HTTPStatus.BAD_REQUEST

        mock_session.get.return_value.content_type = TEST_MIME_TYPE_MP4
        mock_baichuan_vod(reolink_host)

        proxy_url = async_generate_playback_proxy_url(
            config_entry.entry_id,
            TEST_CHANNEL,
            TEST_TIME_RANGE,
            TEST_STREAM,
            VodRequestType.NVR_DOWNLOAD.value,
        )
        response = cast(ClientResponse, await http_client.get(proxy_url))

        assert response.status == 200

    reolink_host.baichuan.get_vod_file_info.assert_not_called()


async def test_playback_proxy_baichuan_too_large(
    hass: HomeAssistant,
    reolink_host: MagicMock,
    config_entry: MockConfigEntry,
    hass_client: ClientSessionGenerator,
    tmp_path: Path,
) -> None:
    """Test a recording too large to cache is played over HTTP instead."""
    mock_baichuan_vod(reolink_host)
    reolink_host.baichuan.get_vod_file_info.return_value = VOD_file_info(
        size=VOD_CACHE_MAX_BYTES + 1,
        handle="0",
        file_id=TEST_FILE_NAME_MP4,
        resolved=True,
        file_type="h264",
        contains_audio=True,
    )
    reolink_host.get_vod_source.return_value = (TEST_MIME_TYPE_MP4, TEST_URL)

    with (
        patch.object(hass.config, "cache_path", return_value=str(tmp_path)),
        patch(
            "homeassistant.components.reolink.views.async_get_clientsession",
            return_value=get_mock_session(),
        ),
    ):
        assert await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()

        proxy_url = async_generate_playback_proxy_url(
            config_entry.entry_id,
            TEST_CHANNEL,
            TEST_FILE_NAME_MP4,
            TEST_STREAM,
            TEST_VOD_TYPE,
        )

        http_client = await hass_client()
        response = cast(ClientResponse, await http_client.get(proxy_url))

        assert response.status == 200

    reolink_host.baichuan.download_vod.assert_not_called()
    reolink_host.get_vod_source.assert_called_once()


async def test_playback_proxy_baichuan_range_request(
    hass: HomeAssistant,
    reolink_host: MagicMock,
    config_entry: MockConfigEntry,
    hass_client: ClientSessionGenerator,
    tmp_path: Path,
) -> None:
    """Test a range request into a recording, which is what seeking uses."""
    mock_baichuan_vod(reolink_host)

    with patch.object(hass.config, "cache_path", return_value=str(tmp_path)):
        assert await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()

        proxy_url = async_generate_playback_proxy_url(
            config_entry.entry_id,
            TEST_CHANNEL,
            TEST_FILE_NAME_MP4,
            TEST_STREAM,
            TEST_VOD_TYPE,
        )

        http_client = await hass_client()
        response = cast(
            ClientResponse,
            await http_client.get(proxy_url, headers={"Range": "bytes=10-19"}),
        )

        assert response.status == HTTPStatus.PARTIAL_CONTENT
        assert await response.content.read() == TEST_VOD_DATA[10:20]


async def test_playback_proxy_baichuan_download_error(
    hass: HomeAssistant,
    reolink_host: MagicMock,
    config_entry: MockConfigEntry,
    hass_client: ClientSessionGenerator,
    tmp_path: Path,
) -> None:
    """Test a failing Baichuan download falls back to HTTP playback."""
    mock_baichuan_vod(reolink_host)

    async def _fail(channel: int, filename: str, **kwargs: Any) -> AsyncIterator[bytes]:
        yield TEST_VOD_DATA[:10]
        raise ReolinkError(TEST_ERROR)

    reolink_host.baichuan.download_vod = Mock(side_effect=_fail)
    reolink_host.get_vod_source.return_value = (TEST_MIME_TYPE_MP4, TEST_URL)

    mock_session = get_mock_session()

    with (
        patch.object(hass.config, "cache_path", return_value=str(tmp_path)),
        patch(
            "homeassistant.components.reolink.views.async_get_clientsession",
            return_value=mock_session,
        ),
    ):
        assert await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()

        proxy_url = async_generate_playback_proxy_url(
            config_entry.entry_id,
            TEST_CHANNEL,
            TEST_FILE_NAME_MP4,
            TEST_STREAM,
            TEST_VOD_TYPE,
        )

        http_client = await hass_client()
        response = cast(ClientResponse, await http_client.get(proxy_url))

        assert response.status == 200
        assert await response.content.read() == b"testtest"

    reolink_host.get_vod_source.assert_called_once()


async def test_playback_proxy_baichuan_conditional_range(
    hass: HomeAssistant,
    reolink_host: MagicMock,
    config_entry: MockConfigEntry,
    hass_client: ClientSessionGenerator,
    tmp_path: Path,
) -> None:
    """Test seeking with If-Range, which needs the validator to stay stable."""
    mock_baichuan_vod(reolink_host)

    with patch.object(hass.config, "cache_path", return_value=str(tmp_path)):
        assert await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()

        proxy_url = async_generate_playback_proxy_url(
            config_entry.entry_id,
            TEST_CHANNEL,
            TEST_FILE_NAME_MP4,
            TEST_STREAM,
            TEST_VOD_TYPE,
        )

        http_client = await hass_client()
        first = cast(ClientResponse, await http_client.get(proxy_url))
        assert first.status == 200
        last_modified = first.headers["Last-Modified"]
        await first.read()

        served_from_cache = cast(ClientResponse, await http_client.get(proxy_url))
        assert served_from_cache.headers["Last-Modified"] == last_modified
        await served_from_cache.read()

        response = cast(
            ClientResponse,
            await http_client.get(
                proxy_url,
                headers={"Range": "bytes=10-19", "If-Range": last_modified},
            ),
        )

        assert response.status == HTTPStatus.PARTIAL_CONTENT
        assert await response.content.read() == TEST_VOD_DATA[10:20]

    assert reolink_host.baichuan.download_vod.call_count == 1
