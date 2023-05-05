"""Test tts."""
from __future__ import annotations

from unittest.mock import patch

from homeassistant.components.wyoming.data import load_wyoming_info
from homeassistant.core import HomeAssistant

from . import STT_INFO, MockAsyncTcpClient


async def test_load_info(hass: HomeAssistant, snapshot) -> None:
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
