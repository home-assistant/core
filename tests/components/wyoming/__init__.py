"""Tests for the Wyoming integration."""

import asyncio
from unittest.mock import patch

from wyoming.event import Event
from wyoming.info import (
    AsrModel,
    AsrProgram,
    Attribution,
    Info,
    Satellite,
    TtsProgram,
    TtsVoice,
    TtsVoiceSpeaker,
    WakeModel,
    WakeProgram,
)

from homeassistant.components.wyoming import DOMAIN
from homeassistant.components.wyoming.devices import SatelliteDevice
from homeassistant.core import HomeAssistant

TEST_ATTR = Attribution(name="Test", url="http://www.test.com")
STT_INFO = Info(
    asr=[
        AsrProgram(
            name="Test ASR",
            description="Test ASR",
            installed=True,
            attribution=TEST_ATTR,
            models=[
                AsrModel(
                    name="Test Model",
                    description="Test Model",
                    installed=True,
                    attribution=TEST_ATTR,
                    languages=["en-US"],
                    version=None,
                )
            ],
            version=None,
        )
    ]
)
TTS_INFO = Info(
    tts=[
        TtsProgram(
            name="Test TTS",
            description="Test TTS",
            installed=True,
            attribution=TEST_ATTR,
            voices=[
                TtsVoice(
                    name="Test Voice",
                    description="Test Voice",
                    installed=True,
                    attribution=TEST_ATTR,
                    languages=["en-US"],
                    speakers=[TtsVoiceSpeaker(name="Test Speaker")],
                    version=None,
                )
            ],
            version=None,
        )
    ]
)
WAKE_WORD_INFO = Info(
    wake=[
        WakeProgram(
            name="Test Wake Word",
            description="Test Wake Word",
            installed=True,
            attribution=TEST_ATTR,
            models=[
                WakeModel(
                    name="Test Model",
                    description="Test Model",
                    phrase="Test Phrase",
                    installed=True,
                    attribution=TEST_ATTR,
                    languages=["en-US"],
                    version=None,
                )
            ],
            version=None,
        )
    ]
)
SATELLITE_INFO = Info(
    satellite=Satellite(
        name="Test Satellite",
        description="Test Satellite",
        installed=True,
        attribution=TEST_ATTR,
        area="Office",
        version=None,
    )
)
EMPTY_INFO = Info()


class MockAsyncTcpClient:
    """Mock AsyncTcpClient."""

    def __init__(self, responses: list[Event]) -> None:
        """Initialize."""
        self.host: str | None = None
        self.port: int | None = None
        self.written: list[Event] = []
        self.responses = responses

    async def connect(self) -> None:
        """Connect."""

    async def write_event(self, event: Event):
        """Send."""
        self.written.append(event)

    async def read_event(self) -> Event | None:
        """Receive."""
        await asyncio.sleep(0)  # force context switch

        if self.responses:
            return self.responses.pop(0)

        return None

    async def __aenter__(self):
        """Enter."""
        return self

    async def __aexit__(self, exc_type, exc, tb):
        """Exit."""

    def __call__(self, host: str, port: int):
        """Call."""
        self.host = host
        self.port = port
        return self


async def reload_satellite(
    hass: HomeAssistant, config_entry_id: str
) -> SatelliteDevice:
    """Reload config entry with satellite info and returns new device."""
    with (
        patch(
            "homeassistant.components.wyoming.data.load_wyoming_info",
            return_value=SATELLITE_INFO,
        ),
        patch(
            "homeassistant.components.wyoming.satellite.WyomingSatellite.run"
        ) as _run_mock,
    ):
        # _run_mock: satellite task does not actually run
        await hass.config_entries.async_reload(config_entry_id)

    return hass.data[DOMAIN][config_entry_id].satellite.device
