"""Tests for the Reolink views platform."""

from http import HTTPStatus
import logging
from typing import Any, cast
from unittest.mock import AsyncMock, MagicMock, Mock, patch

from aiohttp import ClientConnectionError, ClientResponse
import pytest
from pytest_homeassistant.common import MockConfigEntry
from pytest_homeassistant.typing import ClientSessionGenerator
from reolink_aio.enums import VodRequestType
from reolink_aio.exceptions import ReolinkError

from homeassistant.components.reolink.config_flow import DEFAULT_PROTOCOL
from homeassistant.components.reolink.const import CONF_BC_PORT, CONF_USE_HTTPS, DOMAIN
from homeassistant.components.reolink.views import async_generate_playback_proxy_url
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import (
    CONF_HOST,
    CONF_PASSWORD,
    CONF_PORT,
    CONF_PROTOCOL,
    CONF_USERNAME,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import format_mac

from .conftest import (
    TEST_BC_PORT,
    TEST_HOST2,
    TEST_MAC2,
    TEST_NVR_NAME2,
    TEST_PASSWORD2,
    TEST_PORT,
    TEST_USE_HTTPS,
    TEST_USERNAME2,
)

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


async def test_playback_download_fallback_per_channel(
    hass: HomeAssistant,
    reolink_host: MagicMock,
    config_entry: MockConfigEntry,
    hass_client: ClientSessionGenerator,
) -> None:
    """Test the download fallback only applies to the channel that needed it."""
    reolink_host.get_vod_source.return_value = (TEST_MIME_TYPE_MP4, TEST_URL)

    mock_session = Mock()
    mock_session.get = AsyncMock(
        side_effect=[
            get_mock_session(content_type="video/x-flv").get.return_value,
            *(get_mock_session().get.return_value for _ in range(6)),
        ]
    )

    config_entry2 = MockConfigEntry(
        domain=DOMAIN,
        unique_id=format_mac(TEST_MAC2),
        data={
            CONF_HOST: TEST_HOST2,
            CONF_USERNAME: TEST_USERNAME2,
            CONF_PASSWORD: TEST_PASSWORD2,
            CONF_PORT: TEST_PORT,
            CONF_USE_HTTPS: TEST_USE_HTTPS,
            CONF_BC_PORT: TEST_BC_PORT,
        },
        options={
            CONF_PROTOCOL: DEFAULT_PROTOCOL,
        },
        title=TEST_NVR_NAME2,
    )
    config_entry2.add_to_hass(hass)

    with (
        patch("homeassistant.components.reolink.PLATFORMS", []),
        patch(
            "homeassistant.components.reolink.views.async_get_clientsession",
            return_value=mock_session,
        ),
    ):
        assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()
    assert config_entry2.state is ConfigEntryState.LOADED

    http_client = await hass_client()

    async def request(entry_id: str, channel: int, vod_type: VodRequestType) -> None:
        proxy_url = async_generate_playback_proxy_url(
            entry_id, channel, TEST_FILE_NAME_MP4, TEST_STREAM, vod_type.value
        )
        response = await http_client.get(proxy_url)
        assert response.status == 200

    await request(config_entry.entry_id, 0, VodRequestType.PLAYBACK)
    await request(config_entry.entry_id, 0, VodRequestType.PLAYBACK)
    await request(config_entry.entry_id, 1, VodRequestType.PLAYBACK)
    await request(config_entry2.entry_id, 0, VodRequestType.PLAYBACK)
    await request(config_entry.entry_id, 0, VodRequestType.NVR_DOWNLOAD)

    with patch("homeassistant.components.reolink.PLATFORMS", []):
        assert await hass.config_entries.async_reload(config_entry.entry_id)
    await hass.async_block_till_done()

    await request(config_entry.entry_id, 0, VodRequestType.PLAYBACK)

    assert [
        (call.args[0], call.args[3])
        for call in reolink_host.get_vod_source.call_args_list
    ] == [
        (0, VodRequestType.PLAYBACK),
        (0, VodRequestType.DOWNLOAD),
        (0, VodRequestType.DOWNLOAD),
        (1, VodRequestType.PLAYBACK),
        (0, VodRequestType.PLAYBACK),
        (0, VodRequestType.NVR_DOWNLOAD),
        (0, VodRequestType.PLAYBACK),
    ]


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
