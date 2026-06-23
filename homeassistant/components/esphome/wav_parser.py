"""Helper to parse and stream WAV files."""

from collections.abc import AsyncIterable, AsyncIterator
import struct


async def stream_wav(
    stream: AsyncIterable[bytes],
    *,
    expected_format: str = "pcm",
    expected_channels: int,
    expected_width: int,
    expected_sample_rate: int,
    samples_per_chunk: int = 512,
) -> AsyncIterator[tuple[bytes, bool]]:
    """Parse a WAV stream, validate its header, and yield chunks of audio data."""
    if expected_format != "pcm":
        raise ValueError(f"Unsupported expected format: {expected_format}")

    bytes_buffer = bytearray()
    found_data_chunk = False
    fmt_validated = False
    riff_checked = False
    parsing_headers = True

    bytes_per_chunk_payload = samples_per_chunk * expected_width * expected_channels
    data_bytes_remaining = 0
    pending_chunk: bytes | None = None

    async for chunk in stream:
        bytes_buffer.extend(chunk)

        while parsing_headers:
            if not riff_checked:
                if len(bytes_buffer) < 12:
                    break
                riff, _, wave_fmt = struct.unpack("<4sI4s", bytes_buffer[:12])
                if riff != b"RIFF" or wave_fmt != b"WAVE":
                    raise ValueError("Invalid WAV format: missing RIFF/WAVE header")
                riff_checked = True
                del bytes_buffer[:12]

            if len(bytes_buffer) < 8:
                break

            chunk_id, chunk_size = struct.unpack("<4sI", bytes_buffer[:8])

            if chunk_id == b"fmt ":
                if len(bytes_buffer) < 8 + chunk_size:
                    break

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
                if num_channels != expected_channels:
                    raise ValueError(
                        f"Expected {expected_channels} channels, got {num_channels}"
                    )
                if chunk_sample_rate != expected_sample_rate:
                    raise ValueError(
                        f"Expected {expected_sample_rate} Hz, got {chunk_sample_rate} Hz"
                    )
                if bits_per_sample // 8 != expected_width:
                    raise ValueError(
                        f"Expected {expected_width} bytes per sample, got {bits_per_sample // 8}"
                    )

                fmt_validated = True
                del bytes_buffer[: 8 + chunk_size + (chunk_size & 1)]

            elif chunk_id == b"data":
                if not fmt_validated:
                    raise ValueError("WAV missing fmt chunk before data chunk")

                found_data_chunk = True
                data_bytes_remaining = chunk_size
                parsing_headers = False
                del bytes_buffer[:8]
                break
            else:
                padded_size = chunk_size + (chunk_size & 1)
                if len(bytes_buffer) < 8 + padded_size:
                    break
                del bytes_buffer[: 8 + padded_size]

        if found_data_chunk:
            while (
                data_bytes_remaining >= bytes_per_chunk_payload
                and len(bytes_buffer) >= bytes_per_chunk_payload
            ):
                payload = bytes(bytes_buffer[:bytes_per_chunk_payload])
                del bytes_buffer[:bytes_per_chunk_payload]
                data_bytes_remaining -= bytes_per_chunk_payload

                if pending_chunk is not None:
                    yield pending_chunk, False

                pending_chunk = payload

                if data_bytes_remaining == 0:
                    yield pending_chunk, True
                    pending_chunk = None
                    return

    if not found_data_chunk:
        raise ValueError("Invalid WAV format: incomplete or missing data chunk")

    remaining_bytes_to_read = min(data_bytes_remaining, len(bytes_buffer))
    if remaining_bytes_to_read > 0:
        remaining = bytes(bytes_buffer[:remaining_bytes_to_read])
        if pending_chunk is not None:
            yield pending_chunk, False
        pending_chunk = remaining

    if pending_chunk is not None:
        yield pending_chunk, True
