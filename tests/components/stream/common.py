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


def split_hevc_nal_units(data, nal_types):
    """Split an Annex B access unit into the NAL units of the given types and the rest."""
    nal_units = data.split(b"\x00\x00\x01")
    selected = [
        nal_unit for nal_unit in nal_units[1:] if (nal_unit[0] >> 1) & 0x3F in nal_types
    ]
    rest = [nal_units[0]] + [
        nal_unit
        for nal_unit in nal_units[1:]
        if (nal_unit[0] >> 1) & 0x3F not in nal_types
    ]
    return b"".join(b"\x00\x00\x01" + nal_unit for nal_unit in selected), (
        b"\x00\x00\x01".join(rest)
    )


def _rbsp_bits(nal_unit):
    """Return the RBSP bits of a NAL unit without the stop bit and alignment."""
    rbsp = nal_unit[2:].replace(b"\x00\x00\x03", b"\x00\x00")
    return "".join(f"{byte:08b}" for byte in rbsp).rstrip("0")[:-1]


def _nal_unit_from_bits(header, bits):
    """Return a NAL unit from its header and RBSP bits, with emulation prevention."""
    bits += "1"
    bits += "0" * (-len(bits) % 8)
    nal_unit = bytearray(header)
    zeros = 0
    for byte in int(bits, 2).to_bytes(len(bits) // 8):
        if zeros >= 2 and byte <= 3:
            nal_unit.append(3)
            zeros = 0
        nal_unit.append(byte)
        zeros = zeros + 1 if byte == 0 else 0
    return bytes(nal_unit)


def _exp_golomb(value):
    """Return the unsigned Exp-Golomb code of a value."""
    code = f"{value + 1:b}"
    return "0" * (len(code) - 1) + code


def _exp_golomb_end(bits, pos):
    """Return the position after the unsigned Exp-Golomb code at pos."""
    leading_zeros = bits.index("1", pos) - pos
    return pos + 2 * leading_zeros + 1


def hevc_pps_with_id(pps, pps_id, sps_id=0):
    """Return a copy of a PPS NAL unit with its ID and its SPS ID replaced."""
    bits = _rbsp_bits(pps)
    # pps_pic_parameter_set_id, pps_seq_parameter_set_id
    rest = _exp_golomb_end(bits, _exp_golomb_end(bits, 0))
    return _nal_unit_from_bits(
        pps[:2], _exp_golomb(pps_id) + _exp_golomb(sps_id) + bits[rest:]
    )


def hevc_sps_with_id(sps, sps_id):
    """Return a copy of an SPS NAL unit without sub-layers with its ID replaced."""
    bits = _rbsp_bits(sps)
    assert bits[4:7] == "000"  # sps_max_sub_layers_minus1
    # VPS ID, sub-layers and nesting flag (8 bits), profile_tier_level (96 bits)
    pos = 8 + 96
    return _nal_unit_from_bits(
        sps[:2],
        bits[:pos] + _exp_golomb(sps_id) + bits[_exp_golomb_end(bits, pos) :],
    )


def generate_video_with_size_change(
    encoder,
    sizes,
    duration,
    keyframe_vps=True,
    first_size_keyframe_sets=True,
    extra_pps=False,
    change_at_dts_zero=False,
    stale_extradata=False,
    sps_id_switch=False,
    first_size_sar=None,
):
    """Generate an MPEG-TS video whose picture size changes at a keyframe.

    Each size is encoded separately for `duration` seconds and carries its own
    in-band parameter sets, repeated at every keyframe. With `keyframe_vps`
    False, only the first keyframe carries a VPS. With
    `first_size_keyframe_sets` False, the keyframes of the first size carry no
    parameter sets; they come once, ahead of the second packet (the stream's
    extradata), as with a source that sends them out of band. With
    `extra_pps`, the first keyframe (the stream's extradata) also carries a
    copy of its PPS with ID 1, which no later keyframe repeats. With
    `change_at_dts_zero`, timestamps start negative and the first keyframe of
    the second size has DTS 0. With `stale_extradata`, a non-key packet ahead
    of the first keyframe carries the parameter sets of the last size, which
    become the stream's extradata. With `sps_id_switch`, the sizes after the
    first use SPS ID 1. `first_size_sar` is the x265 `sar` of the first size.
    """
    options = {"x265-params": "repeat-headers=1"} if encoder == "libx265" else {}
    parts = [
        av.open(
            generate_video(
                encoder,
                "mpegts",
                duration,
                size,
                {"x265-params": f"repeat-headers=1:sar={first_size_sar}"}
                if first_size_sar and not index
                else options,
            )
        )
        for index, size in enumerate(sizes)
    ]
    part_packets = [
        [packet for packet in part.demux(video=0) if packet.dts is not None]
        for part in parts
    ]
    lengths = [
        packets[-1].dts + packets[-1].duration - packets[0].dts
        for packets in part_packets
    ]
    output = io.BytesIO()
    container = av.open(
        output, mode="w", format="mpegts", options={"avoid_negative_ts": "disabled"}
    )
    stream = container.add_stream_from_template(parts[0].streams.video[0])
    offset = -lengths[0] if change_at_dts_zero else 0
    if stale_extradata:
        parameter_sets, _ = split_hevc_nal_units(
            bytes(part_packets[-1][0]), {32, 33, 34}
        )
        # A non-key access unit, so the stream starts at the next keyframe
        stale = av.Packet(parameter_sets + bytes(part_packets[-1][1]))
        stale.pts = stale.dts = offset - 1
        stale.time_base = part_packets[0][0].time_base
        stale.stream = stream
        container.mux(stale)
    for part_index, (packets, length) in enumerate(
        zip(part_packets, lengths, strict=True)
    ):
        shift = offset - packets[0].dts
        out_of_band = b""
        for packet_index, packet in enumerate(packets):
            first = not part_index and not packet_index
            nal_types = set()
            if not keyframe_vps and not first:
                nal_types.add(32)
            if not first_size_keyframe_sets and not part_index:
                nal_types.update((32, 33, 34))
            data = bytes(packet)
            if nal_types:
                removed, data = split_hevc_nal_units(data, nal_types)
                if first:
                    out_of_band = removed
                elif packet_index == 1:
                    data = out_of_band + data
            if sps_id_switch and part_index and packet.is_keyframe:
                sps, _ = split_hevc_nal_units(data, {33})
                pps, _ = split_hevc_nal_units(data, {34})
                sps, pps = sps[3:].rstrip(b"\x00"), pps[3:].rstrip(b"\x00")
                data = data.replace(sps, hevc_sps_with_id(sps, 1), 1).replace(
                    pps, hevc_pps_with_id(pps, 0, 1), 1
                )
            if extra_pps and first:
                pps, _ = split_hevc_nal_units(data, {34})
                data = data.replace(
                    pps,
                    pps
                    + b"\x00\x00\x01"
                    + hevc_pps_with_id(pps[3:].rstrip(b"\x00"), 1),
                    1,
                )
            if data != bytes(packet):
                stripped = av.Packet(data)
                stripped.pts, stripped.dts = packet.pts, packet.dts
                stripped.time_base = packet.time_base
                stripped.is_keyframe = packet.is_keyframe
                packet = stripped
            packet.pts += shift
            packet.dts += shift
            packet.stream = stream
            container.mux(packet)
        offset += length
    for part in parts:
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
