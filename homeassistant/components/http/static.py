"""Static file handling for HTTP component."""

import re

from aiohttp import hdrs
from aiohttp.web import FileResponse, middleware
from aiohttp.web_exceptions import HTTPNotFound
from aiohttp.web_urldispatcher import StaticResource
from yarl import URL

_FINGERPRINT = re.compile(r'^(.+)-[a-z0-9]{32}\.(\w+)$', re.IGNORECASE)


class CachingStaticResource(StaticResource):
    """Static Resource handler that will add cache headers."""

    async def _handle(self, request):
        filename = URL(request.match_info['filename']).path
        try:
            # PyLint is wrong about resolve not being a member.
            filepath = self._directory.joinpath(filename).resolve()
            if not self._follow_symlinks:
                filepath.relative_to(self._directory)
        except (ValueError, FileNotFoundError) as error:
            # relatively safe
            raise HTTPNotFound() from error
        except Exception as error:
            # perm error or other kind!
            request.app.logger.exception(error)
            raise HTTPNotFound() from error

        if filepath.is_dir():
            return await super()._handle(request)
        elif filepath.is_file():
            return CachingFileResponse(filepath, chunk_size=self._chunk_size)
        else:
            raise HTTPNotFound


# pylint: disable=too-many-ancestors
class CachingFileResponse(FileResponse):
    """FileSender class that caches output if not in dev mode."""

    def __init__(self, *args, **kwargs):
        """Initialize the hass file sender."""
        super().__init__(*args, **kwargs)

        orig_sendfile = self._sendfile

        async def sendfile(request, fobj, count):
            """Sendfile that includes a cache header."""
            cache_time = 31 * 86400  # = 1 month
            self.headers[hdrs.CACHE_CONTROL] = "public, max-age={}".format(
                cache_time)

            await orig_sendfile(request, fobj, count)

        # Overwriting like this because __init__ can change implementation.
        self._sendfile = sendfile


@middleware
async def staticresource_middleware(request, handler):
    """Middleware to strip out fingerprint from fingerprinted assets."""
    path = request.path
    if not path.startswith('/static/') and not path.startswith('/frontend'):
        return await handler(request)

    fingerprinted = _FINGERPRINT.match(request.match_info['filename'])

    if fingerprinted:
        request.match_info['filename'] = \
            '{}.{}'.format(*fingerprinted.groups())

    return await handler(request)
