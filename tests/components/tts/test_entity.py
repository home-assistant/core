"""Tests for the TTS entity."""

from typing import Any

import pytest

from homeassistant.components import tts
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant, State

from .common import (
    DEFAULT_LANG,
    SUPPORT_LANGUAGES,
    TEST_DOMAIN,
    MockTTSEntity,
    mock_config_entry_setup,
)

from tests.common import mock_restore_cache


class DefaultEntity(tts.TextToSpeechEntity):
    """Test entity."""

    _attr_supported_languages = SUPPORT_LANGUAGES
    _attr_default_language = DEFAULT_LANG


async def test_default_entity_attributes() -> None:
    """Test default entity attributes."""
    entity = DefaultEntity()

    assert entity.hass is None
    assert entity.default_language == DEFAULT_LANG
    assert entity.supported_languages == SUPPORT_LANGUAGES
    assert entity.supported_options is None
    assert entity.default_options is None
    assert entity.async_get_supported_voices("test") is None


async def test_restore_state(
    hass: HomeAssistant,
    mock_tts_entity: MockTTSEntity,
) -> None:
    """Test we restore state in the integration."""
    entity_id = f"{tts.DOMAIN}.{TEST_DOMAIN}"
    timestamp = "2023-01-01T23:59:59+00:00"
    mock_restore_cache(hass, (State(entity_id, timestamp),))

    config_entry = await mock_config_entry_setup(hass, mock_tts_entity)
    await hass.async_block_till_done()

    assert config_entry.state is ConfigEntryState.LOADED
    state = hass.states.get(entity_id)
    assert state
    assert state.state == timestamp


async def test_tts_entity_subclass_properties(
    hass: HomeAssistant, caplog: pytest.LogCaptureFixture
) -> None:
    """Test for errors when subclasses of the TextToSpeechEntity are missing required properties."""

    class TestClass1(tts.TextToSpeechEntity):
        _attr_default_language = DEFAULT_LANG
        _attr_supported_languages = SUPPORT_LANGUAGES

    await mock_config_entry_setup(hass, TestClass1())

    class TestClass2(tts.TextToSpeechEntity):
        @property
        def default_language(self) -> str:
            return DEFAULT_LANG

        @property
        def supported_languages(self) -> list[str]:
            return SUPPORT_LANGUAGES

    await mock_config_entry_setup(hass, TestClass2())

    assert all(record.exc_info is None for record in caplog.records)

    caplog.clear()

    class TestClass3(tts.TextToSpeechEntity):
        _attr_default_language = DEFAULT_LANG

    await mock_config_entry_setup(hass, TestClass3())

    assert (
        "TTS entities must either set the '_attr_supported_languages' attribute or override the 'supported_languages' property"
        in [
            str(record.exc_info[1])
            for record in caplog.records
            if record.exc_info is not None
        ]
    )
    caplog.clear()

    class TestClass4(tts.TextToSpeechEntity):
        _attr_supported_languages = SUPPORT_LANGUAGES

    await mock_config_entry_setup(hass, TestClass4())

    assert (
        "TTS entities must either set the '_attr_default_language' attribute or override the 'default_language' property"
        in [
            str(record.exc_info[1])
            for record in caplog.records
            if record.exc_info is not None
        ]
    )
    caplog.clear()

    class TestClass5(tts.TextToSpeechEntity):
        @property
        def default_language(self) -> str:
            return DEFAULT_LANG

    await mock_config_entry_setup(hass, TestClass5())

    assert (
        "TTS entities must either set the '_attr_supported_languages' attribute or override the 'supported_languages' property"
        in [
            str(record.exc_info[1])
            for record in caplog.records
            if record.exc_info is not None
        ]
    )
    caplog.clear()

    class TestClass6(tts.TextToSpeechEntity):
        @property
        def supported_languages(self) -> list[str]:
            return SUPPORT_LANGUAGES

    await mock_config_entry_setup(hass, TestClass6())

    assert (
        "TTS entities must either set the '_attr_default_language' attribute or override the 'default_language' property"
        in [
            str(record.exc_info[1])
            for record in caplog.records
            if record.exc_info is not None
        ]
    )


def test_streaming_supported() -> None:
    """Test streaming support."""
    base_entity = tts.TextToSpeechEntity()
    assert base_entity.supports_streaming_input is False

    class StreamingEntity(tts.TextToSpeechEntity):
        async def async_stream_tts_audio(self) -> None:
            pass

    streaming_entity = StreamingEntity()
    assert streaming_entity.supports_streaming_input is True

    class NonStreamingEntity(tts.TextToSpeechEntity):
        async def async_get_tts_audio(
            self, message: str, language: str, options: dict[str, Any]
        ) -> tts.TtsAudioType:
            pass

    non_streaming_entity = NonStreamingEntity()
    assert non_streaming_entity.supports_streaming_input is False

    class SyncNonStreamingEntity(tts.TextToSpeechEntity):
        def get_tts_audio(
            self, message: str, language: str, options: dict[str, Any]
        ) -> tts.TtsAudioType:
            pass

    sync_non_streaming_entity = SyncNonStreamingEntity()
    assert sync_non_streaming_entity.supports_streaming_input is False
