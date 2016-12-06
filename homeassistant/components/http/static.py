"""Static file handling for HTTP component."""
import asyncio
import mimetypes
import re

from aiohttp import hdrs
from aiohttp.file_sender import FileSender
from aiohttp.web_urldispatcher import StaticResource
from aiohttp.web_exceptions import HTTPNotModified

from .const import KEY_DEVELOPMENT

_FINGERPRINT = re.compile(r'^(.+)-[a-z0-9]{32}\.(\w+)$', re.IGNORECASE)


class GzipFileSender(FileSender):
    """FileSender class capable of sending gzip version if available."""

    # pylint: disable=invalid-name

    @asyncio.coroutine
    def send(self, request, filepath):
        """Send filepath to client using request."""
        gzip = False
        if 'gzip' in request.headers[hdrs.ACCEPT_ENCODING]:
            gzip_path = filepath.with_name(filepath.name + '.gz')

            if gzip_path.is_file():
                filepath = gzip_path
                gzip = True

        st = filepath.stat()

        modsince = request.if_modified_since
        if modsince is not None and st.st_mtime <= modsince.timestamp():
            raise HTTPNotModified()

        ct, encoding = mimetypes.guess_type(str(filepath))
        if not ct:
            ct = 'application/octet-stream'

        resp = self._response_factory()
        resp.content_type = ct
        if encoding:
            resp.headers[hdrs.CONTENT_ENCODING] = encoding
        if gzip:
            resp.headers[hdrs.VARY] = hdrs.ACCEPT_ENCODING
        resp.last_modified = st.st_mtime

        # CACHE HACK
        if not request.app[KEY_DEVELOPMENT]:
            cache_time = 31 * 86400  # = 1 month
            resp.headers[hdrs.CACHE_CONTROL] = "public, max-age={}".format(
                cache_time)

        file_size = st.st_size

        resp.content_length = file_size
        with filepath.open('rb') as f:
            yield from self._sendfile(request, resp, f, file_size)

        return resp


GZIP_FILE_SENDER = GzipFileSender()
FILE_SENDER = FileSender()


@asyncio.coroutine
def staticresource_middleware(app, handler):
    """Enhance StaticResourceHandler middleware.

    Adds gzip encoding and fingerprinting matching.
    """
    inst = getattr(handler, '__self__', None)
    if not isinstance(inst, StaticResource):
        return handler

    # pylint: disable=protected-access
    inst._file_sender = GZIP_FILE_SENDER

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
