"""
Provide functionality to stream MJPEG.

For more details about this component, please refer to the documentation at
https://home-assistant.io/components/stream/mjpg
"""
import asyncio

from aiohttp import web

from . import StreamView
from .core import StreamOutput


async def async_setup_platform(hass):
    """Set up api endpoints."""
    hass.http.register_view(MjpegView())
    return '{}/api/mjpeg/{}'


class MjpegView(StreamView):
    """Stream view to serve a MJPEG stream."""

    url = r'/api/mjpeg/{token:[a-f0-9]+}'
    name = 'api:stream:mjpeg'

    async def handle(self, request, stream, sequence):
        """Return mjpeg stream."""
        track = stream.add_provider(MjpegStreamOutput())
        # Grab first image to make sure it's coming
        segment = await asyncio.wait_for(track.recv(), 1)
        if not segment:
            return web.HTTPNotFound()

        response = web.StreamResponse()
        response.content_type = ('multipart/x-mixed-replace; '
                                 'boundary=--frameboundary')
        await response.prepare(request)

        async def write_to_mjpeg_stream(img_bytes):
            """Write image to stream."""
            await response.write(bytes(
                '--frameboundary\r\n'
                'Content-Type: {}\r\n'
                'Content-Length: {}\r\n\r\n'.format(
                    'image/jpeg', img_bytes.getbuffer().nbytes),
                'utf-8') + img_bytes.getvalue() + b'\r\n')

        while True:
            if self._unsub is None:
                break
            segment = await track.recv()
            if not segment:
                break
            await write_to_mjpeg_stream(segment.segment)

        return response


class MjpegStreamOutput(StreamOutput):
    """Represents HLS Output formats."""

    @property
    def format(self) -> str:
        """Return container format."""
        return 'mjpeg'

    @property
    def video_codec(self) -> str:
        """Return desired video codec."""
        return 'mjpeg'
