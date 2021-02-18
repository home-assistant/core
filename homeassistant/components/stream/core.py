"""Provides core stream functionality."""
import abc
import io
from typing import Callable

from aiohttp import web
import attr

from homeassistant.components.http import HomeAssistantView
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.event import async_call_later

from .const import ATTR_STREAMS, DOMAIN


@attr.s
class StreamBuffer:
    """Represent a segment."""

    segment: io.BytesIO = attr.ib()
    output = attr.ib()  # type=av.OutputContainer
    vstream = attr.ib()  # type=av.VideoStream
    astream = attr.ib(default=None)  # type=Optional[av.AudioStream]


@attr.s
class Segment:
    """Represent a segment."""

    sequence: int = attr.ib()
    segment: io.BytesIO = attr.ib()
    duration: float = attr.ib()
    # For detecting discontinuities across stream restarts
    stream_id: int = attr.ib(default=0)


class IdleTimer:
    """Invoke a callback after an inactivity timeout.

    The IdleTimer invokes the callback after some timeout has passed. The awake() method
    resets the internal alarm, extending the inactivity time.
    """

    def __init__(
        self, hass: HomeAssistant, timeout: int, idle_callback: Callable[[], None]
    ):
        """Initialize IdleTimer."""
        self._hass = hass
        self._timeout = timeout
        self._callback = idle_callback
        self._unsub = None
        self.idle = False

    def start(self):
        """Start the idle timer if not already started."""
        self.idle = False
        if self._unsub is None:
            self._unsub = async_call_later(self._hass, self._timeout, self.fire)

    def awake(self):
        """Keep the idle time alive by resetting the timeout."""
        self.idle = False
        # Reset idle timeout
        self.clear()
        self._unsub = async_call_later(self._hass, self._timeout, self.fire)

    def clear(self):
        """Clear and disable the timer if it has not already fired."""
        if self._unsub is not None:
            self._unsub()

    def fire(self, _now=None):
        """Invoke the idle timeout callback, called when the alarm fires."""
        self.idle = True
        self._unsub = None
        self._callback()


class StreamOutput(abc.ABC):
    """Represents a stream output."""

    def __init__(self, hass: HomeAssistant):
        """Initialize a stream output."""
        self._hass = hass

    @property
    def container_options(self) -> Callable[[int], dict]:
        """Return Callable which takes a sequence number and returns container options."""
        return None

    def put(self, segment: Segment) -> None:
        """Store output."""
        self._hass.loop.call_soon_threadsafe(self._async_put, segment)

    @callback
    def _async_put(self, segment: Segment) -> None:
        """Store output from event loop."""


class StreamView(HomeAssistantView):
    """
    Base StreamView.

    For implementation of a new stream format, define `url` and `name`
    attributes, and implement `handle` method in a child class.
    """

    requires_auth = False
    platform = None

    async def get(self, request, token, sequence=None):
        """Start a GET request."""
        hass = request.app["hass"]

        stream = next(
            (s for s in hass.data[DOMAIN][ATTR_STREAMS] if s.access_token == token),
            None,
        )

        if not stream:
            raise web.HTTPNotFound()

        # Start worker if not already started
        stream.start()

        return await self.handle(request, stream, sequence)

    async def handle(self, request, stream, sequence):
        """Handle the stream request."""
        raise NotImplementedError()
