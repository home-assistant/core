"""Test the ESPHome WAV parser helper."""

from collections.abc import AsyncIterable
import io
import struct
import wave

import pytest

from homeassistant.components.esphome.wav_parser import stream_wav


def _create_wav(
    channels: int = 1,
    sample_width: int = 2,
    sample_rate: int = 16000,
    data: bytes = b"\x00" * 1024,
) -> bytes:
    """Create a valid WAV file in bytes."""
    with io.BytesIO() as wav_io:
        with wave.open(wav_io, "wb") as wav_file:
            wav_file.setframerate(sample_rate)
            wav_file.setsampwidth(sample_width)
            wav_file.setnchannels(channels)
            wav_file.writeframes(data)
        return wav_io.getvalue()


async def _async_generator(data: bytes, chunk_size: int = 128) -> AsyncIterable[bytes]:
    """Yield bytes in chunks."""
    for i in range(0, len(data), chunk_size):
        yield data[i : i + chunk_size]


async def test_stream_wav_valid() -> None:
    """Test streaming a valid WAV file."""
    audio_data = b"\x01\x02\x03\x04" * 256  # 1024 bytes
    wav_bytes = _create_wav(data=audio_data)

    chunks = []
    async for chunk, is_last in stream_wav(
        _async_generator(wav_bytes, chunk_size=100),
        expected_format="pcm",
        expected_channels=1,
        expected_width=2,
        expected_sample_rate=16000,
        samples_per_chunk=256,
    ):
        chunks.append((chunk, is_last))

    # samples_per_chunk = 256, expected_width = 2, expected_channels = 1
    # bytes_per_chunk = 256 * 2 * 1 = 512 bytes
    # total audio data = 1024 bytes -> exactly 2 chunks of 512 bytes
    assert len(chunks) == 2
    assert chunks[0] == (audio_data[:512], False)
    assert chunks[1] == (audio_data[512:], True)


async def test_stream_wav_unsupported_format() -> None:
    """Test streaming with an unsupported format."""
    wav_bytes = _create_wav()
    with pytest.raises(ValueError, match="Unsupported expected format"):
        async for _, _ in stream_wav(
            _async_generator(wav_bytes),
            expected_format="mp3",
            expected_channels=1,
            expected_width=2,
            expected_sample_rate=16000,
        ):
            pass


async def test_stream_wav_invalid_header() -> None:
    """Test streaming with an invalid WAV header."""
    invalid_wav = b"RIFFinvalidheader"
    with pytest.raises(
        ValueError, match="Invalid WAV format: missing RIFF/WAVE header"
    ):
        async for _, _ in stream_wav(
            _async_generator(invalid_wav),
            expected_channels=1,
            expected_width=2,
            expected_sample_rate=16000,
        ):
            pass


async def test_stream_wav_missing_data_chunk() -> None:
    """Test streaming a WAV that is missing data chunk."""
    # Write only a fmt chunk
    header = b"RIFF" + struct.pack("<I", 24) + b"WAVE"
    fmt_chunk = (
        b"fmt "
        + struct.pack("<I", 16)
        + struct.pack("<HHIIHH", 1, 1, 16000, 32000, 2, 16)
    )
    wav_bytes = header + fmt_chunk
    with pytest.raises(
        ValueError, match="Invalid WAV format: incomplete or missing data chunk"
    ):
        async for _, _ in stream_wav(
            _async_generator(wav_bytes),
            expected_channels=1,
            expected_width=2,
            expected_sample_rate=16000,
        ):
            pass


async def test_stream_wav_fmt_validation() -> None:
    """Test parameter validation against fmt chunk."""
    wav_bytes = _create_wav(channels=1, sample_width=2, sample_rate=16000)

    # Wrong channels
    with pytest.raises(ValueError, match="Expected 2 channels, got 1"):
        async for _, _ in stream_wav(
            _async_generator(wav_bytes),
            expected_channels=2,
            expected_width=2,
            expected_sample_rate=16000,
        ):
            pass

    # Wrong width
    with pytest.raises(ValueError, match="Expected 4 bytes per sample, got 2"):
        async for _, _ in stream_wav(
            _async_generator(wav_bytes),
            expected_channels=1,
            expected_width=4,
            expected_sample_rate=16000,
        ):
            pass

    # Wrong sample rate
    with pytest.raises(ValueError, match="Expected 8000 Hz, got 16000 Hz"):
        async for _, _ in stream_wav(
            _async_generator(wav_bytes),
            expected_channels=1,
            expected_width=2,
            expected_sample_rate=8000,
        ):
            pass


async def test_stream_wav_non_pcm() -> None:
    """Test non-PCM WAV format."""
    header = b"RIFF" + struct.pack("<I", 36) + b"WAVE"
    # Format code 3 is IEEE Float (non-PCM)
    fmt_chunk = (
        b"fmt "
        + struct.pack("<I", 16)
        + struct.pack("<HHIIHH", 3, 1, 16000, 64000, 4, 32)
    )
    data_chunk = b"data" + struct.pack("<I", 100)
    wav_bytes = header + fmt_chunk + data_chunk
    with pytest.raises(ValueError, match="Can only stream PCM WAV, got format 3"):
        async for _, _ in stream_wav(
            _async_generator(wav_bytes),
            expected_channels=1,
            expected_width=4,
            expected_sample_rate=16000,
        ):
            pass


async def test_stream_wav_missing_fmt_chunk() -> None:
    """Test streaming data chunk without fmt chunk."""
    header = b"RIFF" + struct.pack("<I", 20) + b"WAVE"
    data_chunk = b"data" + struct.pack("<I", 100)
    wav_bytes = header + data_chunk
    with pytest.raises(ValueError, match="WAV missing fmt chunk before data chunk"):
        async for _, _ in stream_wav(
            _async_generator(wav_bytes),
            expected_channels=1,
            expected_width=2,
            expected_sample_rate=16000,
        ):
            pass


async def test_stream_wav_small_fmt_chunk() -> None:
    """Test when fmt chunk size is less than 16."""
    header = b"RIFF" + struct.pack("<I", 20) + b"WAVE"
    fmt_chunk = b"fmt " + struct.pack("<I", 10) + b"\x00" * 10
    wav_bytes = header + fmt_chunk
    with pytest.raises(ValueError, match="WAV fmt chunk too small: 10 bytes"):
        async for _, _ in stream_wav(
            _async_generator(wav_bytes),
            expected_channels=1,
            expected_width=2,
            expected_sample_rate=16000,
        ):
            pass


async def test_stream_wav_trailing_data() -> None:
    """Test streaming a WAV file where audio data size is not a multiple of chunk size."""
    audio_data = b"\x01\x02\x03\x04" * 150  # 600 bytes
    wav_bytes = _create_wav(data=audio_data)

    chunks = []
    async for chunk, is_last in stream_wav(
        _async_generator(wav_bytes, chunk_size=100),
        expected_format="pcm",
        expected_channels=1,
        expected_width=2,
        expected_sample_rate=16000,
        samples_per_chunk=256,  # 512 bytes per chunk
    ):
        chunks.append((chunk, is_last))

    # First chunk: 512 bytes, not last
    # Second chunk: 88 bytes, last
    assert len(chunks) == 2
    assert chunks[0] == (audio_data[:512], False)
    assert chunks[1] == (audio_data[512:], True)


async def test_stream_wav_small_chunks() -> None:
    """Test streaming a WAV file in very small chunks to test partial header parsing."""
    audio_data = b"\x01\x02\x03\x04" * 256  # 1024 bytes
    wav_bytes = _create_wav(data=audio_data)

    chunks = []
    async for chunk, is_last in stream_wav(
        _async_generator(wav_bytes, chunk_size=5),
        expected_format="pcm",
        expected_channels=1,
        expected_width=2,
        expected_sample_rate=16000,
        samples_per_chunk=256,
    ):
        chunks.append((chunk, is_last))

    assert len(chunks) == 2
    assert chunks[0] == (audio_data[:512], False)
    assert chunks[1] == (audio_data[512:], True)


async def test_stream_wav_odd_fmt_chunk() -> None:
    """Test streaming a WAV file with an odd-sized fmt chunk where the pad byte is in a separate chunk."""
    header = b"RIFF" + struct.pack("<I", 36) + b"WAVE"
    fmt_chunk = (
        b"fmt "
        + struct.pack("<I", 17)
        + struct.pack("<HHIIHH", 1, 1, 16000, 32000, 2, 16)
        + b"\x00"
    )
    pad_byte = b"\x00"
    data_chunk = b"data" + struct.pack("<I", 4) + b"\x01\x02\x03\x04"

    part1 = header + fmt_chunk
    part2 = pad_byte + data_chunk

    async def stream_generator() -> AsyncIterable[bytes]:
        yield part1
        yield part2

    chunks = []
    async for chunk, is_last in stream_wav(
        stream_generator(),
        expected_channels=1,
        expected_width=2,
        expected_sample_rate=16000,
        samples_per_chunk=2,
    ):
        chunks.append((chunk, is_last))

    assert len(chunks) == 1
    assert chunks[0] == (b"\x01\x02\x03\x04", True)
