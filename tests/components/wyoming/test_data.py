"""Test tts."""
from __future__ import annotations

from unittest.mock import patch

from syrupy.assertion import SnapshotAssertion

from homeassistant.components.wyoming.data import WyomingService, load_wyoming_info
from homeassistant.core import HomeAssistant

from . import SATELLITE_INFO, STT_INFO, TTS_INFO, WAKE_WORD_INFO, MockAsyncTcpClient


async def test_load_info(hass: HomeAssistant, snapshot: SnapshotAssertion) -> None:
    """Test loading info."""
    with patch(
        "homeassistant.components.wyoming.data.AsyncTcpClient",
        MockAsyncTcpClient([STT_INFO.event()]),
    ) as mock_client:
        info = await load_wyoming_info("localhost", 1234)

    assert info == STT_INFO
    assert mock_client.written == snapshot


async def test_load_info_oserror(hass: HomeAssistant) -> None:
    """Test loading info and error raising."""
    mock_client = MockAsyncTcpClient([STT_INFO.event()])

    with patch(
        "homeassistant.components.wyoming.data.AsyncTcpClient",
        mock_client,
    ), patch.object(mock_client, "read_event", side_effect=OSError("Boom!")):
        info = await load_wyoming_info(
            "localhost",
            1234,
            retries=0,
            retry_wait=0,
            timeout=0.001,
        )

    assert info is None


async def test_service_name(hass: HomeAssistant) -> None:
    """Test loading service info."""
    with patch(
        "homeassistant.components.wyoming.data.AsyncTcpClient",
        MockAsyncTcpClient([STT_INFO.event()]),
    ):
        service = await WyomingService.create("localhost", 1234)
        assert service is not None
        assert service.get_name() == STT_INFO.asr[0].name

    with patch(
        "homeassistant.components.wyoming.data.AsyncTcpClient",
        MockAsyncTcpClient([TTS_INFO.event()]),
    ):
        service = await WyomingService.create("localhost", 1234)
        assert service is not None
        assert service.get_name() == TTS_INFO.tts[0].name

    with patch(
        "homeassistant.components.wyoming.data.AsyncTcpClient",
        MockAsyncTcpClient([WAKE_WORD_INFO.event()]),
    ):
        service = await WyomingService.create("localhost", 1234)
        assert service is not None
        assert service.get_name() == WAKE_WORD_INFO.wake[0].name

    with patch(
        "homeassistant.components.wyoming.data.AsyncTcpClient",
        MockAsyncTcpClient([SATELLITE_INFO.event()]),
    ):
        service = await WyomingService.create("localhost", 1234)
        assert service is not None
        assert service.get_name() == SATELLITE_INFO.satellite.name
