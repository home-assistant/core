"""Collection of test helpers."""

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
from homeassistant.util import dt as dt_util

FAKE_TIME = dt_util.utcnow()

# Segment with defaults filled in for use in tests
DefaultSegment = partial(
    Segment,
    init=None,
    stream_id=0,
    start_time=FAKE_TIME,
    _stream_outputs=[],
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
    color = [
        np.round(
            255 * (0.5 + 0.5 * np.sin(2 * np.pi * (c / 3 + frame_i / total_frames)))
        )
        for c in range(3)
    ]
    return np.full((480, 320, 3), color, dtype=np.uint8)


def generate_video(encoder, container_format, duration, size=(480, 320), options=None):
    """Generate a test video.

    See: http://docs.mikeboers.com/pyav/develop/cookbook/numpy.html
    """

    fps = 24
    total_frames = duration * fps

    output = io.BytesIO()
    output.name = "test.mov" if container_format == "mov" else "test.mp4"
    container = av.open(output, mode="w", format=container_format)

    stream = container.add_stream(encoder, rate=fps)
    stream.width, stream.height = size
    stream.pix_fmt = "yuv420p"
    stream.options.update({"g": str(fps), "keyint_min": str(fps), **(options or {})})

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


def strip_hevc_vps(data):
    """Return an Annex B access unit without its VPS NAL units."""
    nal_units = data.split(b"\x00\x00\x01")
    return b"\x00\x00\x01".join(
        nal_unit
        for i, nal_unit in enumerate(nal_units)
        if i == 0 or (nal_unit[0] >> 1) & 0x3F != 32
    )


def generate_video_with_size_change(encoder, sizes, duration, keyframe_vps=True):
    """Generate an MPEG-TS video whose picture size changes at a keyframe.

    Each size is encoded separately for `duration` seconds and carries its own
    in-band parameter sets, repeated at every keyframe. With `keyframe_vps`
    False, only the first keyframe carries a VPS.
    """
    options = {"x265-params": "repeat-headers=1"} if encoder == "libx265" else {}
    output = io.BytesIO()
    container = av.open(output, mode="w", format="mpegts")
    stream = None
    offset = 0
    for size in sizes:
        part = av.open(generate_video(encoder, "mpegts", duration, size, options))
        if stream is None:
            stream = container.add_stream_from_template(part.streams.video[0])
        packets = [packet for packet in part.demux(video=0) if packet.dts is not None]
        shift = offset - packets[0].dts
        for packet in packets:
            if not keyframe_vps and (offset or packet is not packets[0]):
                stripped = av.Packet(strip_hevc_vps(bytes(packet)))
                stripped.pts, stripped.dts = packet.pts, packet.dts
                stripped.time_base = packet.time_base
                stripped.is_keyframe = packet.is_keyframe
                packet = stripped
            packet.pts += shift
            packet.dts += shift
            packet.stream = stream
            container.mux(packet)
        offset = packets[-1].dts + shift + packets[-1].duration
        part.close()
    container.close()
    output.seek(0)
    return output


def remux_with_audio(source, container_format, audio_codec):
    """Remux an existing source with new audio."""
    av_source = av.open(source, mode="r")
    output = io.BytesIO()
    output.name = "test.mov" if container_format == "mov" else "test.mp4"
    container = av.open(output, mode="w", format=container_format)
    container.add_stream_from_template(av_source.streams.video[0])

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
