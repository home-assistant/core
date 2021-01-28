"""The tests for stream."""
from unittest.mock import AsyncMock, MagicMock, PropertyMock, patch

import pytest

from homeassistant.components.stream import create_stream
from homeassistant.components.stream.const import (
    ATTR_STREAMS,
    CONF_LOOKBACK,
    CONF_STREAM_ID,
    DOMAIN,
    SERVICE_RECORD,
)
from homeassistant.const import CONF_FILENAME
from homeassistant.exceptions import HomeAssistantError
from homeassistant.setup import async_setup_component

STREAM_SOURCE = "rtsp://my.video"
STREAM_ID = "stream_id"


async def test_record_service_invalid_file(hass):
    """Test record service call with invalid file."""
    await async_setup_component(hass, "stream", {"stream": {}})

    create_stream(hass, STREAM_ID, STREAM_SOURCE)
    data = {CONF_STREAM_ID: STREAM_ID, CONF_FILENAME: "/my/invalid/path"}
    with pytest.raises(HomeAssistantError):
        await hass.services.async_call(DOMAIN, SERVICE_RECORD, data, blocking=True)


async def test_record_service_init_stream(hass):
    """Test record service call with invalid file."""
    await async_setup_component(hass, "stream", {"stream": {}})
    data = {CONF_STREAM_ID: STREAM_ID, CONF_FILENAME: "/my/invalid/path"}
    with patch("homeassistant.components.stream.Stream") as stream_mock, patch.object(
        hass.config, "is_allowed_path", return_value=True
    ):
        # Setup stubs
        stream_mock.return_value.outputs = {}

        create_stream(hass, STREAM_ID, STREAM_SOURCE)

        # Call Service
        await hass.services.async_call(DOMAIN, SERVICE_RECORD, data, blocking=True)

        # Assert
        assert stream_mock.called


async def test_record_service_existing_record_session(hass):
    """Test record service call with existing record session."""
    await async_setup_component(hass, "stream", {"stream": {}})
    data = {CONF_STREAM_ID: STREAM_ID, CONF_FILENAME: "/my/invalid/path"}

    # Setup stubs
    stream_mock = MagicMock()
    type(stream_mock).source = PropertyMock(return_value=STREAM_SOURCE)
    stream_mock.return_value.outputs = {"recorder": MagicMock()}
    hass.data[DOMAIN][ATTR_STREAMS][STREAM_ID] = stream_mock

    with patch.object(hass.config, "is_allowed_path", return_value=True), pytest.raises(
        HomeAssistantError
    ):

        # Call Service
        await hass.services.async_call(DOMAIN, SERVICE_RECORD, data, blocking=True)


async def test_record_service_lookback(hass):
    """Test record service lookback."""
    await async_setup_component(hass, "stream", {"stream": {}})
    data = {
        CONF_STREAM_ID: STREAM_ID,
        CONF_FILENAME: "/my/invalid/path",
        CONF_LOOKBACK: 4,
    }

    with patch("homeassistant.components.stream.Stream") as stream_mock, patch.object(
        hass.config, "is_allowed_path", return_value=True
    ):
        # Setup stubs
        hls_mock = MagicMock()
        hls_mock.target_duration = 2
        hls_mock.recv = AsyncMock(return_value=None)
        stream_mock.return_value.outputs = {"hls": hls_mock}

        create_stream(hass, STREAM_ID, STREAM_SOURCE)

        # Call Service
        await hass.services.async_call(DOMAIN, SERVICE_RECORD, data, blocking=True)

        assert stream_mock.called
        stream_mock.return_value.add_provider.assert_called_once_with(
            "recorder", timeout=30
        )
        assert hls_mock.recv.called
