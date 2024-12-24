"""Tests for the Reolink views platform."""

from http import HTTPStatus
import logging
from typing import cast
from unittest.mock import AsyncMock, MagicMock, Mock, patch

from aiohttp import ClientResponse
import pytest
from reolink_aio.enums import VodRequestType
from reolink_aio.exceptions import ReolinkError

from homeassistant.components.reolink.views import async_generate_playback_proxy_url
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry
from tests.typing import ClientSessionGenerator

TEST_YEAR = 2023
TEST_MONTH = 11
TEST_DAY = 14
TEST_DAY2 = 15
TEST_HOUR = 13
TEST_MINUTE = 12
TEST_FILE_NAME_MP4 = f"{TEST_YEAR}{TEST_MONTH}{TEST_DAY}{TEST_HOUR}{TEST_MINUTE}00.mp4"
TEST_STREAM = "sub"
TEST_CHANNEL = "0"
TEST_VOD_TYPE = VodRequestType.PLAYBACK.value
TEST_MIME_TYPE_MP4 = "video/mp4"
TEST_URL = "http://test_url&token=test"
TEST_ERROR = "TestError"


async def test_playback_proxy(
    hass: HomeAssistant,
    reolink_connect: MagicMock,
    config_entry: MockConfigEntry,
    hass_client: ClientSessionGenerator,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test successful playback proxy URL."""
    reolink_connect.get_vod_source.return_value = (TEST_MIME_TYPE_MP4, TEST_URL)

    content = Mock()
    content.__anext__ = AsyncMock(side_effect=[b"test", b"test", StopAsyncIteration()])
    content.__aiter__ = Mock(return_value=content)

    mock_response = Mock()
    mock_response.content_length = 8
    mock_response.content.iter_chunked = Mock(return_value=content)

    mock_session = Mock()
    mock_session.request = AsyncMock(return_value=mock_response)

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
    reolink_connect: MagicMock,
    config_entry: MockConfigEntry,
    hass_client: ClientSessionGenerator,
) -> None:
    """Test error while getting source for playback proxy URL."""
    reolink_connect.get_vod_source.side_effect = ReolinkError(TEST_ERROR)

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
    reolink_connect.get_vod_source.side_effect = None


async def test_playback_proxy_timeout(
    hass: HomeAssistant,
    reolink_connect: MagicMock,
    config_entry: MockConfigEntry,
    hass_client: ClientSessionGenerator,
) -> None:
    """Test playback proxy URL with a timeout in the second chunk."""
    reolink_connect.get_vod_source.return_value = (TEST_MIME_TYPE_MP4, TEST_URL)

    content = Mock()
    content.__anext__ = AsyncMock(side_effect=[b"test", TimeoutError()])
    content.__aiter__ = Mock(return_value=content)

    mock_response = Mock()
    mock_response.content_length = 4
    mock_response.content.iter_chunked = Mock(return_value=content)

    mock_session = Mock()
    mock_session.request = AsyncMock(return_value=mock_response)

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
