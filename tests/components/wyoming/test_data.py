"""Test tts."""

import asyncio
from unittest.mock import patch

import pytest
from syrupy.assertion import SnapshotAssertion
from wyoming.event import Event
from wyoming.info import Info

from homeassistant.components.wyoming.data import (
    _INFO_TIMEOUT,
    WyomingService,
    load_wyoming_info,
)
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

    with (
        patch(
            "homeassistant.components.wyoming.data.AsyncTcpClient",
            mock_client,
        ),
        patch.object(mock_client, "read_event", side_effect=OSError("Boom!")),
    ):
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


async def test_satellite_with_wake_word(hass: HomeAssistant) -> None:
    """Test that wake word info with satellite doesn't overwrite the service name."""
    # Info for local wake word detection
    satellite_info = Info(
        satellite=SATELLITE_INFO.satellite,
        wake=WAKE_WORD_INFO.wake,
    )

    with patch(
        "homeassistant.components.wyoming.data.AsyncTcpClient",
        MockAsyncTcpClient([satellite_info.event()]),
    ):
        service = await WyomingService.create("localhost", 1234)
        assert service is not None
        assert service.get_name() == satellite_info.satellite.name
        assert not service.platforms


class SlowMockAsyncTcpClient(MockAsyncTcpClient):
    """Mock client that delays its response to simulate a busy satellite."""

    def __init__(self, responses: list[Event | None], delay: float) -> None:
        """Initialize."""
        super().__init__(responses)
        self._delay = delay

    async def read_event(self) -> Event | None:
        """Receive after a delay."""
        await asyncio.sleep(self._delay)
        return await super().read_event()


def test_info_timeout_is_relaxed() -> None:
    """Test the default info timeout tolerates satellites busy on connect.

    Some satellites do not answer the initial Describe immediately (e.g. while
    playing a startup sound), so the default must be generous enough to avoid
    spurious setup failures.
    """
    assert _INFO_TIMEOUT >= 5


@pytest.mark.parametrize(
    ("timeout", "expect_loaded"),
    [(0.05, False), (0.5, True)],
    ids=["too_short", "long_enough"],
)
async def test_load_info_timeout_governs_slow_satellite(
    hass: HomeAssistant, timeout: float, expect_loaded: bool
) -> None:
    """Test a slow satellite loads only when the timeout is generous enough."""
    with patch(
        "homeassistant.components.wyoming.data.AsyncTcpClient",
        SlowMockAsyncTcpClient([STT_INFO.event()], delay=0.2),
    ):
        info = await load_wyoming_info(
            "localhost", 1234, retries=0, retry_wait=0, timeout=timeout
        )

    assert (info is not None) == expect_loaded
