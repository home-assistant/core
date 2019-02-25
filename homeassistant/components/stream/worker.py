"""Proides the worker thread needed for processing streams."""
import asyncio
from fractions import Fraction
import io

from .core import Segment, StreamBuffer


def generate_audio_frame():
    """Generate a blank audio frame."""
    from av import AudioFrame
    audio_frame = AudioFrame(format='dbl', layout='mono', samples=1024)
    audio_bytes = b''.join(b'\x00\x00\x00\x00\x00\x00\x00\x00'
                           for i in range(0, 1024))
    audio_frame.planes[0].update(audio_bytes)
    audio_frame.sample_rate = 44100
    audio_frame.time_base = Fraction(1, 44100)
    return audio_frame


def create_stream_buffer(stream_output, video_stream, audio_frame):
    """Create a new StreamBuffer."""
    import av
    a_packet = None
    segment = io.BytesIO()
    output = av.open(
        segment, mode='w', format=stream_output.format)
    vstream = output.add_stream(
        stream_output.video_codec, video_stream.rate)
    # Fix format
    vstream.codec_context.format = \
        video_stream.codec_context.format
    # Check if audio is requested
    astream = None
    if stream_output.audio_codec:
        astream = output.add_stream(
            stream_output.audio_codec, 44100)
        # Need to do it multiple times for some reason
        while not a_packet:
            a_packets = astream.encode(audio_frame)
            if a_packets:
                a_packet = a_packets[0]
    return (a_packet, StreamBuffer(segment, output, vstream, astream))


def stream_worker(hass, stream, quit_event):
    """Handle consuming streams."""
    try:
        video_stream = stream.container.streams.video[0]
    except (KeyError, IndexError):
        hass.getLogger().error("Stream has no video")
        return

    audio_frame = generate_audio_frame()

    outputs = {}
    first_packet = True
    sequence = 1
    audio_packets = {}

    while not quit_event.is_set():
        packet = next(stream.container.demux(video_stream))

        # We need to skip the "flushing" packets that `demux` generates.
        if packet.dts is None:
            continue

        # Mux on every keyframe
        if packet.is_keyframe and not first_packet:
            segment_duration = (packet.pts * packet.time_base) / sequence
            for fmt, buffer in outputs.items():
                buffer.output.close()
                del audio_packets[buffer.astream]
                asyncio.run_coroutine_threadsafe(
                    stream.outputs[fmt].put(Segment(
                        sequence, buffer.segment, segment_duration
                    )), hass.loop)
            outputs = {}
            sequence += 1

            # Initialize outputs on keyframes as well
            if not outputs:
                for stream_output in stream.outputs.values():
                    if video_stream.name != stream_output.video_codec:
                        continue

                    a_packet, buffer = create_stream_buffer(
                        stream_output, video_stream, audio_frame)
                    audio_packets[buffer.astream] = a_packet
                    outputs[stream_output.format] = buffer

        # First video packet tends to have a weird dts/pts
        if first_packet:
            packet.dts = 0
            packet.pts = 0
            first_packet = False

        # We need to assign the packet to the new stream.
        for buffer in outputs.values():
            if audio_packets.get(buffer.astream):
                a_packet = audio_packets[buffer.astream]
                a_time_base = a_packet.time_base
                video_start = packet.pts * packet.time_base
                video_duration = packet.duration * packet.time_base
                if packet.is_keyframe:
                    a_packet.pts = int(video_start / a_time_base)
                    a_packet.dts = int(video_start / a_time_base)
                # Adjust pts
                target_pts = int((video_start + video_duration) / a_time_base)
                while a_packet.pts < target_pts:
                    buffer.output.mux(a_packet)
                    a_packet.pts += a_packet.duration
                    a_packet.dts += a_packet.duration
                    audio_packets[buffer.astream] = a_packet

            packet.stream = buffer.vstream
            buffer.output.mux(packet)
