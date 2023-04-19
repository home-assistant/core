"""Tests for the Wyoming integration."""
from wyoming.info import AsrModel, AsrProgram, Attribution, Info

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
EMPTY_INFO = Info()
