"""Audio processing."""

from typing import Literal

import ffmpeg


class AudioProcessor:
    """General processing of the .pct input stream."""

    def __init__(self, mode: Literal["1", "2"], format: str, input_rate: int) -> None:
        """Set processing values."""
        self.mode = mode
        self.format = format
        self.input_rate = input_rate

    def process_stream(self, data: bytes) -> bytes:
        """Process raw pcm audio and return raw wav data."""
        process = (
            ffmpeg.input("pipe:0", format=self.format, ar=self.input_rate, ac=self.mode)
            .output("pipe:1", format="wav")
            .overwrite_output()
            .run_async(pipe_stdin=True, pipe_stdout=True, pipe_stderr=True)
        )

        stdout, stderr = process.communicate(input=data)
        if process.returncode != 0:
            _raise_ffmpeg_error(stderr)
        return stdout


def _raise_ffmpeg_error(stderr: bytes):
    """Raise a RuntimeError for FFmpeg errors."""
    raise RuntimeError(f"FFmpeg error: {stderr.decode()}")
