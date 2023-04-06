"""Test Voice Assistant init."""

from syrupy.assertion import SnapshotAssertion

from homeassistant.components import stt, voice_assistant
from homeassistant.core import HomeAssistant


async def test_pipeline_from_audio_stream(
    hass: HomeAssistant, mock_stt_provider, init_components, snapshot: SnapshotAssertion
) -> None:
    """Test creating a pipeline from an audio stream."""

    events = []

    async def audio_data():
        yield b"part1"
        yield b"part2"
        yield b""

    await voice_assistant.async_pipeline_from_audio_stream(
        hass,
        events.append,
        stt.SpeechMetadata(
            language="",
            format=stt.AudioFormats.WAV,
            codec=stt.AudioCodecs.PCM,
            bit_rate=stt.AudioBitRates.BITRATE_16,
            sample_rate=stt.AudioSampleRates.SAMPLERATE_16000,
            channel=stt.AudioChannels.CHANNEL_MONO,
        ),
        audio_data(),
    )

    processed = []
    for event in events:
        as_dict = event.as_dict()
        as_dict.pop("timestamp")
        processed.append(as_dict)

    assert processed == snapshot
    assert mock_stt_provider.received == [b"part1", b"part2"]
