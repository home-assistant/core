"""Test stt."""

import asyncio
from unittest.mock import patch

import pytest
from syrupy.assertion import SnapshotAssertion
from wyoming.asr import Transcript
from wyoming.error import Error
from wyoming.info import Info, WakeModel, WakeProgram
from wyoming.wake import Detection

from homeassistant.components import wake_word
from homeassistant.components.wyoming.coordinator import UPDATE_INTERVAL
from homeassistant.core import HomeAssistant
from homeassistant.util import dt as dt_util

from . import TEST_ATTR, MockAsyncTcpClient

from tests.common import async_fire_time_changed


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


@pytest.mark.usefixtures("init_wyoming_wake_word")
@pytest.mark.parametrize(
    ("error_code", "expected_message"),
    [
        pytest.param(None, "Error from Wyoming service: Boom!", id="without_code"),
        pytest.param(
            "ModelNotFoundError",
            "Error from Wyoming service: Boom! (code: ModelNotFoundError)",
            id="with_code",
        ),
    ],
)
async def test_streaming_audio_error_event(
    hass: HomeAssistant,
    caplog: pytest.LogCaptureFixture,
    error_code: str | None,
    expected_message: str,
) -> None:
    """Test that an error event from the service is reported."""
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
        MockAsyncTcpClient([Error(text="Boom!", code=error_code).event()]),
    ):
        result = await entity.async_process_audio_stream(audio_stream(), None)

    assert result is None
    assert expected_message in caplog.text


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

    # Different Wyoming info will be fetched on the next refresh
    with patch(
        "homeassistant.components.wyoming.coordinator.load_wyoming_info",
        return_value=new_info,
    ):
        async_fire_time_changed(hass, dt_util.utcnow() + UPDATE_INTERVAL)
        await hass.async_block_till_done()

    assert (await entity.get_supported_wake_words()) == [
        wake_word.WakeWord("ww1", "Wake Word 1", "Wake Word Phrase 1"),
        wake_word.WakeWord("ww2", "Wake Word 2", "Wake Word Phrase 2"),
    ]


@pytest.mark.usefixtures("init_wyoming_wake_word")
async def test_uninstalled_wake_service_skipped(hass: HomeAssistant) -> None:
    """Test that wake words are taken from an installed program."""
    entity = wake_word.async_get_wake_word_detection_entity(
        hass, "wake_word.test_wake_word"
    )
    assert entity is not None

    new_info = Info(
        wake=[
            WakeProgram(
                name="not-installed",
                description="Not Installed",
                installed=False,
                attribution=TEST_ATTR,
                models=[
                    WakeModel(
                        name="unavailable",
                        description="Unavailable",
                        phrase="Unavailable Phrase",
                        installed=False,
                        attribution=TEST_ATTR,
                        languages=[],
                        version=None,
                    )
                ],
                version=None,
            ),
            WakeProgram(
                name="installed",
                description="Installed",
                installed=True,
                attribution=TEST_ATTR,
                models=[
                    WakeModel(
                        name="available",
                        description="Available",
                        phrase="Available Phrase",
                        installed=True,
                        attribution=TEST_ATTR,
                        languages=[],
                        version=None,
                    )
                ],
                version=None,
            ),
        ]
    )

    with patch(
        "homeassistant.components.wyoming.coordinator.load_wyoming_info",
        return_value=new_info,
    ):
        async_fire_time_changed(hass, dt_util.utcnow() + UPDATE_INTERVAL)
        await hass.async_block_till_done()

    assert (await entity.get_supported_wake_words()) == [
        wake_word.WakeWord("available", "Available", "Available Phrase")
    ]
