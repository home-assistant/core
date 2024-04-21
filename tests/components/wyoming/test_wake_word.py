"""Test stt."""

from __future__ import annotations

import asyncio
from unittest.mock import patch

from syrupy.assertion import SnapshotAssertion
from wyoming.asr import Transcript
from wyoming.info import Info, WakeModel, WakeProgram
from wyoming.wake import Detection

from homeassistant.components import wake_word
from homeassistant.core import HomeAssistant

from . import TEST_ATTR, MockAsyncTcpClient


async def test_support(hass: HomeAssistant, init_wyoming_wake_word) -> None:
    """Test supported properties."""
    state = hass.states.get("wake_word.test_wake_word")
    assert state is not None

    entity = wake_word.async_get_wake_word_detection_entity(
        hass, "wake_word.test_wake_word"
    )
    assert entity is not None

    assert (await entity.get_supported_wake_words()) == [
        wake_word.WakeWord(id="Test Model", name="Test Model", phrase="Test Phrase")
    ]


async def test_streaming_audio(
    hass: HomeAssistant, init_wyoming_wake_word, snapshot: SnapshotAssertion
) -> None:
    """Test streaming audio."""
    entity = wake_word.async_get_wake_word_detection_entity(
        hass, "wake_word.test_wake_word"
    )
    assert entity is not None

    async def audio_stream():
        yield b"chunk", 0

        # Delay to force a pending audio chunk
        await asyncio.sleep(0.05)
        yield b"chunk", 1

    client_events = [
        Transcript("not a wake word event").event(),
        Detection(name="Test Model", timestamp=0).event(),
    ]

    with patch(
        "homeassistant.components.wyoming.wake_word.AsyncTcpClient",
        MockAsyncTcpClient(client_events),
    ):
        result = await entity.async_process_audio_stream(audio_stream(), None)

    assert result is not None
    assert result == snapshot
    assert result.wake_word_id == "Test Model"
    assert result.wake_word_phrase == "Test Phrase"


async def test_streaming_audio_connection_lost(
    hass: HomeAssistant, init_wyoming_wake_word
) -> None:
    """Test streaming audio and losing connection."""
    entity = wake_word.async_get_wake_word_detection_entity(
        hass, "wake_word.test_wake_word"
    )
    assert entity is not None

    async def audio_stream():
        # Delay to force a pending audio chunk
        await asyncio.sleep(0.05)
        yield b"chunk", 1

    with patch(
        "homeassistant.components.wyoming.wake_word.AsyncTcpClient",
        MockAsyncTcpClient([None]),
    ):
        result = await entity.async_process_audio_stream(audio_stream(), None)

    assert result is None


async def test_streaming_audio_oserror(
    hass: HomeAssistant, init_wyoming_wake_word
) -> None:
    """Test streaming audio and error raising."""
    entity = wake_word.async_get_wake_word_detection_entity(
        hass, "wake_word.test_wake_word"
    )
    assert entity is not None

    async def audio_stream():
        yield b"chunk1", 1000

    mock_client = MockAsyncTcpClient(
        [Detection(name="Test Model", timestamp=1000).event()]
    )

    with (
        patch(
            "homeassistant.components.wyoming.wake_word.AsyncTcpClient",
            mock_client,
        ),
        patch.object(mock_client, "read_event", side_effect=OSError("Boom!")),
    ):
        result = await entity.async_process_audio_stream(audio_stream(), None)

    assert result is None


async def test_detect_message_with_wake_word(
    hass: HomeAssistant, init_wyoming_wake_word
) -> None:
    """Test that specifying a wake word id produces a Detect message with that id."""
    entity = wake_word.async_get_wake_word_detection_entity(
        hass, "wake_word.test_wake_word"
    )
    assert entity is not None

    async def audio_stream():
        yield b"chunk1", 1000

    mock_client = MockAsyncTcpClient(
        [Detection(name="my-wake-word", timestamp=1000).event()]
    )

    with patch(
        "homeassistant.components.wyoming.wake_word.AsyncTcpClient",
        mock_client,
    ):
        result = await entity.async_process_audio_stream(audio_stream(), "my-wake-word")

    assert isinstance(result, wake_word.DetectionResult)
    assert result.wake_word_id == "my-wake-word"


async def test_detect_message_with_wrong_wake_word(
    hass: HomeAssistant, init_wyoming_wake_word
) -> None:
    """Test that specifying a wake word id filters invalid detections."""
    entity = wake_word.async_get_wake_word_detection_entity(
        hass, "wake_word.test_wake_word"
    )
    assert entity is not None

    async def audio_stream():
        yield b"chunk1", 1000

    mock_client = MockAsyncTcpClient(
        [Detection(name="not-my-wake-word", timestamp=1000).event()],
    )

    with patch(
        "homeassistant.components.wyoming.wake_word.AsyncTcpClient",
        mock_client,
    ):
        result = await entity.async_process_audio_stream(audio_stream(), "my-wake-word")

    assert result is None


async def test_dynamic_wake_word_info(
    hass: HomeAssistant, init_wyoming_wake_word
) -> None:
    """Test that supported wake words are loaded dynamically."""
    entity = wake_word.async_get_wake_word_detection_entity(
        hass, "wake_word.test_wake_word"
    )
    assert entity is not None

    # Original info
    assert (await entity.get_supported_wake_words()) == [
        wake_word.WakeWord("Test Model", "Test Model", "Test Phrase")
    ]

    new_info = Info(
        wake=[
            WakeProgram(
                name="dynamic",
                description="Dynamic Wake Word",
                installed=True,
                attribution=TEST_ATTR,
                models=[
                    WakeModel(
                        name="ww1",
                        description="Wake Word 1",
                        phrase="Wake Word Phrase 1",
                        installed=True,
                        attribution=TEST_ATTR,
                        languages=[],
                        version=None,
                    ),
                    WakeModel(
                        name="ww2",
                        description="Wake Word 2",
                        phrase="Wake Word Phrase 2",
                        installed=True,
                        attribution=TEST_ATTR,
                        languages=[],
                        version=None,
                    ),
                ],
                version=None,
            )
        ]
    )

    # Different Wyoming info will be fetched
    with patch(
        "homeassistant.components.wyoming.wake_word.load_wyoming_info",
        return_value=new_info,
    ):
        assert (await entity.get_supported_wake_words()) == [
            wake_word.WakeWord("ww1", "Wake Word 1", "Wake Word Phrase 1"),
            wake_word.WakeWord("ww2", "Wake Word 2", "Wake Word Phrase 2"),
        ]
