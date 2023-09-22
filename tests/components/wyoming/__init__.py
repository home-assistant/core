"""Tests for the Wyoming integration."""
import asyncio

from wyoming.info import (
    AsrModel,
    AsrProgram,
    Attribution,
    Info,
    TtsProgram,
    TtsVoice,
    TtsVoiceSpeaker,
    WakeModel,
    WakeProgram,
)

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
                )
            ],
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
                )
            ],
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
                    installed=True,
                    attribution=TEST_ATTR,
                    languages=["en-US"],
                )
            ],
        )
    ]
)
EMPTY_INFO = Info()


class MockAsyncTcpClient:
    """Mock AsyncTcpClient."""

    def __init__(self, responses) -> None:
        """Initialize."""
        self.host = None
        self.port = None
        self.written = []
        self.responses = responses

    async def write_event(self, event):
        """Send."""
        self.written.append(event)

    async def read_event(self):
        """Receive."""
        await asyncio.sleep(0)  # force context switch
        return self.responses.pop(0)

    async def __aenter__(self):
        """Enter."""
        return self

    async def __aexit__(self, exc_type, exc, tb):
        """Exit."""

    def __call__(self, host, port):
        """Call."""
        self.host = host
        self.port = port
        return self
