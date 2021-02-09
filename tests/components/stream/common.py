"""Collection of test helpers."""
from fractions import Fraction
import io

import av
import numpy as np

AUDIO_SAMPLE_RATE = 8000


def generate_h264_video(container_format="mp4", audio_codec=None):
    """
    Generate a test video.

    See: http://docs.mikeboers.com/pyav/develop/cookbook/numpy.html
    """

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

    duration = 5
    fps = 24
    total_frames = duration * fps

    output = io.BytesIO()
    output.name = "test.mov" if container_format == "mov" else "test.mp4"
    container = av.open(output, mode="w", format=container_format)

    stream = container.add_stream("libx264", rate=fps)
    stream.width = 480
    stream.height = 320
    stream.pix_fmt = "yuv420p"

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

    for frame_i in range(total_frames):

        img = np.empty((480, 320, 3))
        img[:, :, 0] = 0.5 + 0.5 * np.sin(2 * np.pi * (0 / 3 + frame_i / total_frames))
        img[:, :, 1] = 0.5 + 0.5 * np.sin(2 * np.pi * (1 / 3 + frame_i / total_frames))
        img[:, :, 2] = 0.5 + 0.5 * np.sin(2 * np.pi * (2 / 3 + frame_i / total_frames))

        img = np.round(255 * img).astype(np.uint8)
        img = np.clip(img, 0, 255)

        frame = av.VideoFrame.from_ndarray(img, format="rgb24")
        for packet in stream.encode(frame):
            container.mux(packet)

        if a_packet is not None:
            a_packet.pts = int(frame_i / (fps * a_packet.time_base))
            while a_packet.pts * a_packet.time_base * fps < frame_i + 1:
                a_packet.dts = a_packet.pts
                if (
                    a_packet.dts > last_a_dts
                ):  # avoid writing same dts twice in case of rounding
                    container.mux(a_packet)
                    last_a_dts = a_packet.dts
                a_packet.pts += a_packet.duration

    # Flush stream
    for packet in stream.encode():
        container.mux(packet)

    # Close the file
    container.close()
    output.seek(0)

    return output
