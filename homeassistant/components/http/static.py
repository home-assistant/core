"""Static file handling for HTTP component."""
import asyncio
import re

from aiohttp import hdrs
from aiohttp.file_sender import FileSender
from aiohttp.web_urldispatcher import StaticResource
from .const import KEY_DEVELOPMENT

_FINGERPRINT = re.compile(r'^(.+)-[a-z0-9]{32}\.(\w+)$', re.IGNORECASE)


class CachingFileSender(FileSender):
    """FileSender class that caches output if not in dev mode."""

    def __init__(self, *args, **kwargs):
        """Initialize the hass file sender."""
        super().__init__(*args, **kwargs)

        orig_sendfile = self._sendfile

        @asyncio.coroutine
        def sendfile(request, resp, fobj, count):
            """Sendfile that includes a cache header."""
            if not request.app[KEY_DEVELOPMENT]:
                cache_time = 31 * 86400  # = 1 month
                resp.headers[hdrs.CACHE_CONTROL] = "public, max-age={}".format(
                    cache_time)

            yield from orig_sendfile(request, resp, fobj, count)

        # Overwriting like this because __init__ can change implementation.
        self._sendfile = sendfile


FILE_SENDER = FileSender()
CACHING_FILE_SENDER = CachingFileSender()


@asyncio.coroutine
def staticresource_middleware(app, handler):
    """Enhance StaticResourceHandler middleware.

    Adds gzip encoding and fingerprinting matching.
    """
    inst = getattr(handler, '__self__', None)
    if not isinstance(inst, StaticResource):
        return handler

    # pylint: disable=protected-access
    inst._file_sender = CACHING_FILE_SENDER

    @asyncio.coroutine
    def static_middleware_handler(request):
        """Strip out fingerprints from resource names."""
        fingerprinted = _FINGERPRINT.match(request.match_info['filename'])

        if fingerprinted:
            request.match_info['filename'] = \
                '{}.{}'.format(*fingerprinted.groups())

        resp = yield from handler(request)
        return resp

    return static_middleware_handler
