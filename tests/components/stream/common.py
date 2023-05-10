"""Collection of test helpers."""
from datetime import datetime
from fractions import Fraction
import functools
from functools import partial
import io

import av
import numpy as np

from homeassistant.components.camera import DynamicStreamSettings
from homeassistant.components.stream.core import Orientation, Segment
from homeassistant.components.stream.fmp4utils import (
    TRANSFORM_MATRIX_TOP,
    XYW_ROW,
    find_box,
)

FAKE_TIME = datetime.utcnow()

# Segment with defaults filled in for use in tests
DefaultSegment = partial(
    Segment,
    init=None,
    stream_id=0,
    start_time=FAKE_TIME,
    stream_outputs=[],
)

AUDIO_SAMPLE_RATE = 8000


def stream_teardown():
    """Perform test teardown."""
    frame_image_data.cache_clear()


def generate_audio_frame(pcm_mulaw=False):
    """Generate a blank audio frame."""
    if pcm_mulaw:
        audio_frame = av.AudioFrame(format="s16", layout="mono", samples=1)
        audio_bytes = b"\x00\x00"
    else:
        audio_frame = av.AudioFrame(format="dbl", layout="mono", samples=1024)
        audio_bytes = b"\x00\x00\x00\x00\x00\x00\x00\x00" * 1024
    audio_frame.planes[0].update(audio_bytes)
    audio_frame.sample_rate = AUDIO_SAMPLE_RATE
    audio_frame.time_base = Fraction(1, AUDIO_SAMPLE_RATE)
    return audio_frame


@functools.lru_cache(maxsize=1024)
def frame_image_data(frame_i, total_frames):
    """Generate image content for a frame of a video."""
    img = np.empty((480, 320, 3))
    img[:, :, 0] = 0.5 + 0.5 * np.sin(2 * np.pi * (0 / 3 + frame_i / total_frames))
    img[:, :, 1] = 0.5 + 0.5 * np.sin(2 * np.pi * (1 / 3 + frame_i / total_frames))
    img[:, :, 2] = 0.5 + 0.5 * np.sin(2 * np.pi * (2 / 3 + frame_i / total_frames))

    img = np.round(255 * img).astype(np.uint8)
    img = np.clip(img, 0, 255)
    return img


def generate_video(encoder, container_format, duration):
    """Generate a test video.

    See: http://docs.mikeboers.com/pyav/develop/cookbook/numpy.html
    """

    fps = 24
    total_frames = duration * fps

    output = io.BytesIO()
    output.name = "test.mov" if container_format == "mov" else "test.mp4"
    container = av.open(output, mode="w", format=container_format)

    stream = container.add_stream(encoder, rate=fps)
    stream.width = 480
    stream.height = 320
    stream.pix_fmt = "yuv420p"
    stream.options.update({"g": str(fps), "keyint_min": str(fps)})

    for frame_i in range(total_frames):
        img = frame_image_data(frame_i, total_frames)
        frame = av.VideoFrame.from_ndarray(img, format="rgb24")
        for packet in stream.encode(frame):
            container.mux(packet)

    # Flush stream
    for packet in stream.encode():
        container.mux(packet)

    # Close the file
    container.close()
    output.seek(0)

    return output


def generate_h264_video(container_format="mp4", duration=5):
    """Generate a test video with libx264."""
    return generate_video("libx264", container_format, duration)


def generate_h265_video(container_format="mp4", duration=5):
    """Generate a test video with libx265."""
    return generate_video("libx265", container_format, duration)


def remux_with_audio(source, container_format, audio_codec):
    """Remux an existing source with new audio."""
    av_source = av.open(source, mode="r")
    output = io.BytesIO()
    output.name = "test.mov" if container_format == "mov" else "test.mp4"
    container = av.open(output, mode="w", format=container_format)
    container.add_stream(template=av_source.streams.video[0])

    a_packet = None
    last_a_dts = -1
    if audio_codec is not None:
        if audio_codec == "empty":  # empty we add a stream but don't mux any audio
            astream = container.add_stream("aac", AUDIO_SAMPLE_RATE)
        else:
            astream = container.add_stream(audio_codec, AUDIO_SAMPLE_RATE)
            # Need to do it multiple times for some reason
            while not a_packet:
                a_packets = astream.encode(
                    generate_audio_frame(pcm_mulaw=audio_codec == "pcm_mulaw")
                )
                if a_packets:
                    a_packet = a_packets[0]

    # open original source and iterate through video packets
    for packet in av_source.demux(video=0):
        if not packet.dts:
            continue
        container.mux(packet)
        if a_packet is not None:
            a_packet.pts = int(packet.dts * packet.time_base / a_packet.time_base)
            while (
                a_packet.pts * a_packet.time_base
                < (packet.dts + packet.duration) * packet.time_base
            ):
                a_packet.dts = a_packet.pts
                if (
                    a_packet.dts > last_a_dts
                ):  # avoid writing same dts twice in case of rounding
                    container.mux(a_packet)
                    last_a_dts = a_packet.dts
                a_packet.pts += a_packet.duration

    # Close the file
    container.close()
    output.seek(0)

    return output


def assert_mp4_has_transform_matrix(mp4: bytes, orientation: Orientation):
    """Assert that the mp4 (or init) has the proper transformation matrix."""
    # Find moov
    moov_location = next(find_box(mp4, b"moov"))
    mvhd_location = next(find_box(mp4, b"trak", moov_location))
    tkhd_location = next(find_box(mp4, b"tkhd", mvhd_location))
    tkhd_length = int.from_bytes(
        mp4[tkhd_location : tkhd_location + 4], byteorder="big"
    )
    assert (
        mp4[tkhd_location + tkhd_length - 44 : tkhd_location + tkhd_length - 8]
        == TRANSFORM_MATRIX_TOP[orientation] + XYW_ROW
    )


def dynamic_stream_settings():
    """Create new dynamic stream settings."""
    return DynamicStreamSettings()
