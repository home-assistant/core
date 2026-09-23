"""Helper to parse and stream WAV files."""

import asyncio
from collections.abc import AsyncIterable, AsyncIterator
import struct

import audioop  # pylint: disable=deprecated-module


class WAVHeaderParser:
    """Helper to parse WAV headers from a byte buffer."""

    def __init__(
        self,
        expected_channels: int,
        expected_width: int,
        expected_sample_rate: int,
        allow_pcm_conversion: bool = False,
    ) -> None:
        """Initialize the WAV header parser."""
        self.expected_channels = expected_channels
        self.expected_width = expected_width
        self.expected_sample_rate = expected_sample_rate
        self.allow_pcm_conversion = allow_pcm_conversion
        self.riff_checked = False
        self.fmt_validated = False
        self.data_bytes_remaining = 0
        self.found_data = False
        self.channels: int | None = None
        self.width: int | None = None
        self.sample_rate: int | None = None

    def parse(self, bytes_buffer: bytearray) -> bool:
        """Parse headers from the buffer. Returns True if headers are fully parsed."""
        while True:
            if not self.riff_checked:
                if len(bytes_buffer) < 12:
                    return False
                riff, _, wave_fmt = struct.unpack("<4sI4s", bytes_buffer[:12])
                if riff != b"RIFF" or wave_fmt != b"WAVE":
                    raise ValueError("Invalid WAV format: missing RIFF/WAVE header")
                self.riff_checked = True
                del bytes_buffer[:12]

            if len(bytes_buffer) < 8:
                return False

            chunk_id, chunk_size = struct.unpack("<4sI", bytes_buffer[:8])

            if chunk_id == b"fmt ":
                if len(bytes_buffer) < 8 + chunk_size + (chunk_size & 1):
                    return False

                if chunk_size < 16:
                    raise ValueError(f"WAV fmt chunk too small: {chunk_size} bytes")

                (
                    audio_format,
                    num_channels,
                    chunk_sample_rate,
                    _,
                    _,
                    bits_per_sample,
                ) = struct.unpack("<HHIIHH", bytes_buffer[8:24])

                if audio_format != 1:
                    raise ValueError(
                        f"Can only stream PCM WAV, got format {audio_format}"
                    )
                if num_channels not in (1, 2):
                    raise ValueError(
                        f"Can only stream mono or stereo WAV, got {num_channels} channels"
                    )
                sample_width = bits_per_sample // 8
                if sample_width not in (1, 2, 3, 4):
                    raise ValueError(
                        f"Unsupported PCM sample width: {sample_width} bytes"
                    )
                if (
                    not self.allow_pcm_conversion
                    and num_channels != self.expected_channels
                ):
                    raise ValueError(
                        f"Expected {self.expected_channels} channels, got {num_channels}"
                    )
                if (
                    not self.allow_pcm_conversion
                    and chunk_sample_rate != self.expected_sample_rate
                ):
                    raise ValueError(
                        f"Expected {self.expected_sample_rate} Hz, got {chunk_sample_rate} Hz"
                    )
                if (
                    not self.allow_pcm_conversion
                    and sample_width != self.expected_width
                ):
                    raise ValueError(
                        f"Expected {self.expected_width} bytes per sample, got {sample_width}"
                    )

                self.channels = num_channels
                self.width = sample_width
                self.sample_rate = chunk_sample_rate
                self.fmt_validated = True
                del bytes_buffer[: 8 + chunk_size + (chunk_size & 1)]

            elif chunk_id == b"data":
                if not self.fmt_validated:
                    raise ValueError("WAV missing fmt chunk before data chunk")

                self.data_bytes_remaining = chunk_size
                self.found_data = True
                del bytes_buffer[:8]
                return True
            else:
                padded_size = chunk_size + (chunk_size & 1)
                if len(bytes_buffer) < 8 + padded_size:
                    return False
                del bytes_buffer[: 8 + padded_size]


async def _stream_resampled_wav(
    stream: AsyncIterator[bytes],
    parser: WAVHeaderParser,
    bytes_buffer: bytearray,
    *,
    expected_channels: int,
    expected_width: int,
    expected_sample_rate: int,
    samples_per_chunk: int,
    audio_interrupt: asyncio.Event | None,
) -> AsyncIterator[tuple[bytes, bool]]:
    """Resample parsed PCM data and yield fixed-size output chunks."""
    assert parser.channels is not None
    assert parser.width is not None
    assert parser.sample_rate is not None
    source_frame_size = parser.width * parser.channels
    bytes_per_chunk = samples_per_chunk * expected_width * expected_channels
    converted_buffer = bytearray()
    pending_chunk: bytes | None = None
    rate_state = None

    def discard_buffered_audio() -> None:
        nonlocal pending_chunk, rate_state
        if audio_interrupt is None or not audio_interrupt.is_set():
            return
        parser.data_bytes_remaining -= len(bytes_buffer)
        bytes_buffer.clear()
        converted_buffer.clear()
        pending_chunk = None
        rate_state = None
        audio_interrupt.clear()

    while parser.data_bytes_remaining > 0:
        source_bytes = min(parser.data_bytes_remaining, len(bytes_buffer))
        source_bytes -= source_bytes % source_frame_size
        if source_bytes:
            converted = bytes(bytes_buffer[:source_bytes])
            del bytes_buffer[:source_bytes]
            parser.data_bytes_remaining -= source_bytes

            if parser.width == 1:
                converted = audioop.bias(converted, 1, -128)
            if parser.channels == 2 and expected_channels == 1:
                converted = audioop.tomono(converted, parser.width, 0.5, 0.5)
            elif parser.channels == 1 and expected_channels == 2:
                converted = audioop.tostereo(converted, parser.width, 1, 1)
            if parser.sample_rate != expected_sample_rate:
                converted, rate_state = audioop.ratecv(
                    converted,
                    parser.width,
                    expected_channels,
                    parser.sample_rate,
                    expected_sample_rate,
                    rate_state,
                )
            if parser.width != expected_width:
                converted = audioop.lin2lin(converted, parser.width, expected_width)
            if expected_width == 1:
                converted = audioop.bias(converted, 1, 128)
            converted_buffer.extend(converted)

        while len(converted_buffer) >= bytes_per_chunk:
            payload = bytes(converted_buffer[:bytes_per_chunk])
            del converted_buffer[:bytes_per_chunk]
            if pending_chunk is not None:
                yield pending_chunk, False
                if audio_interrupt is not None and audio_interrupt.is_set():
                    discard_buffered_audio()
                    break
            pending_chunk = payload

        if parser.data_bytes_remaining == 0:
            break

        try:
            chunk = await anext(stream)
        except StopAsyncIteration:
            break
        discard_buffered_audio()
        bytes_buffer.extend(chunk)

    if converted_buffer:
        if pending_chunk is not None:
            yield pending_chunk, False
            if audio_interrupt is not None and audio_interrupt.is_set():
                discard_buffered_audio()
                return
        pending_chunk = bytes(converted_buffer)

    if pending_chunk is not None:
        yield pending_chunk, True


async def stream_wav(
    stream: AsyncIterable[bytes],
    *,
    expected_format: str = "pcm",
    expected_channels: int,
    expected_width: int,
    expected_sample_rate: int,
    samples_per_chunk: int = 512,
    audio_interrupt: asyncio.Event | None = None,
    allow_pcm_conversion: bool = False,
) -> AsyncIterator[tuple[bytes, bool]]:
    """Parse a WAV stream, validate its header, and yield chunks of audio data."""
    if expected_format != "pcm":
        raise ValueError(f"Unsupported expected format: {expected_format}")

    parser = WAVHeaderParser(
        expected_channels,
        expected_width,
        expected_sample_rate,
        allow_pcm_conversion,
    )
    bytes_buffer = bytearray()
    bytes_per_chunk_payload = samples_per_chunk * expected_width * expected_channels
    pending_chunk: bytes | None = None

    def discard_buffered_audio() -> None:
        nonlocal pending_chunk
        if audio_interrupt is None or not audio_interrupt.is_set():
            return
        if not parser.found_data:
            audio_interrupt.clear()
            return
        parser.data_bytes_remaining -= len(bytes_buffer)
        bytes_buffer.clear()
        pending_chunk = None
        audio_interrupt.clear()

    stream_iterator = aiter(stream)
    async for chunk in stream_iterator:
        discard_buffered_audio()
        bytes_buffer.extend(chunk)

        if not parser.found_data and not parser.parse(bytes_buffer):
            continue

        assert parser.sample_rate is not None
        if (
            parser.sample_rate != expected_sample_rate
            or parser.channels != expected_channels
            or parser.width != expected_width
        ):
            async for output in _stream_resampled_wav(
                stream_iterator,
                parser,
                bytes_buffer,
                expected_channels=expected_channels,
                expected_width=expected_width,
                expected_sample_rate=expected_sample_rate,
                samples_per_chunk=samples_per_chunk,
                audio_interrupt=audio_interrupt,
            ):
                yield output
            return

        while (
            parser.data_bytes_remaining >= bytes_per_chunk_payload
            and len(bytes_buffer) >= bytes_per_chunk_payload
        ):
            payload = bytes(bytes_buffer[:bytes_per_chunk_payload])
            del bytes_buffer[:bytes_per_chunk_payload]
            parser.data_bytes_remaining -= bytes_per_chunk_payload

            if pending_chunk is not None:
                yield pending_chunk, False
                if audio_interrupt is not None and audio_interrupt.is_set():
                    discard_buffered_audio()
                    break

            pending_chunk = payload

            if parser.data_bytes_remaining == 0:
                yield pending_chunk, True
                pending_chunk = None
                return

    discard_buffered_audio()
    if not parser.found_data:
        raise ValueError("Invalid WAV format: incomplete or missing data chunk")

    remaining_bytes_to_read = min(parser.data_bytes_remaining, len(bytes_buffer))
    if remaining_bytes_to_read > 0:
        remaining = bytes(bytes_buffer[:remaining_bytes_to_read])
        if pending_chunk is not None:
            yield pending_chunk, False
            if audio_interrupt is not None and audio_interrupt.is_set():
                discard_buffered_audio()
                return
        pending_chunk = remaining

    if pending_chunk is not None:
        yield pending_chunk, True
