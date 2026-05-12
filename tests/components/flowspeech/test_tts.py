"""Tests for the FlowSpeech TTS platform."""

from dataclasses import dataclass

from homeassistant.components.flowspeech.tts import FlowSpeechTTSEntity


@dataclass
class _Result:
    audio_format: str = "wav"
    audio: bytes = b"audio"


class _Client:
    def synthesize(self, message, *, voice):
        assert message == "hello"
        assert voice == "Kore"
        return _Result()


async def test_tts_entity_uses_configured_voice(hass, mock_config_entry):
    """Test TTS synthesis."""
    mock_config_entry.runtime_data = _Client()
    entity = FlowSpeechTTSEntity(mock_config_entry)
    entity.hass = hass

    audio_format, audio = await entity.async_get_tts_audio("hello", "en", {})

    assert audio_format == "wav"
    assert audio == b"audio"
