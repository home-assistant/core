"""Tests for the Wyoming integration."""
from wyoming.info import AsrModel, AsrProgram, Attribution, Info, TtsProgram, TtsVoice

TEST_ATTR = Attribution(name="Test", url="http://www.test.com")
STT_INFO = Info(
    asr=[
        AsrProgram(
            name="Test ASR",
            installed=True,
            attribution=TEST_ATTR,
            models=[
                AsrModel(
                    name="Test Model",
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
            installed=True,
            attribution=TEST_ATTR,
            voices=[
                TtsVoice(
                    name="Test Voice",
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
