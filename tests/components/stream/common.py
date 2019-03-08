"""Collection of test helpers."""
import io

from homeassistant.components.stream import Stream
from homeassistant.components.stream.const import (
    DOMAIN, ATTR_STREAMS)


def generate_h264_video():
    """
    Generate a test video.

    See: http://docs.mikeboers.com/pyav/develop/cookbook/numpy.html
    """
    import numpy as np
    import av

    duration = 5
    fps = 24
    total_frames = duration * fps

    output = io.BytesIO()
    output.name = 'test.ts'
    container = av.open(output, mode='w')

    stream = container.add_stream('libx264', rate=fps)
    stream.width = 480
    stream.height = 320
    stream.pix_fmt = 'yuv420p'

    for frame_i in range(total_frames):

        img = np.empty((480, 320, 3))
        img[:, :, 0] = 0.5 + 0.5 * np.sin(
            2 * np.pi * (0 / 3 + frame_i / total_frames))
        img[:, :, 1] = 0.5 + 0.5 * np.sin(
            2 * np.pi * (1 / 3 + frame_i / total_frames))
        img[:, :, 2] = 0.5 + 0.5 * np.sin(
            2 * np.pi * (2 / 3 + frame_i / total_frames))

        img = np.round(255 * img).astype(np.uint8)
        img = np.clip(img, 0, 255)

        frame = av.VideoFrame.from_ndarray(img, format='rgb24')
        for packet in stream.encode(frame):
            container.mux(packet)

    # Flush stream
    for packet in stream.encode():
        container.mux(packet)

    # Close the file
    container.close()
    output.seek(0)

    return output


def preload_stream(hass, stream_source):
    """Preload a stream for use in tests."""
    stream = Stream(hass, stream_source)
    hass.data[DOMAIN][ATTR_STREAMS][stream_source] = stream
    return stream
