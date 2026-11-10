"""Static file handling for HTTP component."""

from collections.abc import Mapping
from pathlib import Path
from typing import Final, override

from aiohttp.abc import AbstractStreamWriter, BaseRequest
from aiohttp.hdrs import CACHE_CONTROL, CONTENT_TYPE
from aiohttp.web import FileResponse, Request, StreamResponse
from aiohttp.web_fileresponse import CONTENT_TYPES, FALLBACK_CONTENT_TYPE
from aiohttp.web_urldispatcher import StaticResource
from lru import LRU

from homeassistant.helpers.http import KEY_HASS

CACHE_TIME: Final = 31 * 86400  # = 1 month
CACHE_HEADER = f"public, max-age={CACHE_TIME}"
CACHE_HEADERS: Mapping[str, str] = {CACHE_CONTROL: CACHE_HEADER}
RESPONSE_CACHE: LRU[tuple[str, Path], tuple[Path, str]] = LRU(512)

_GUESSER = CONTENT_TYPES.guess_file_type


class _CacheableFileResponse(FileResponse):
    """FileResponse that sends the cache header only for successful responses.

    The header is attached in _start(), which runs after FileResponse.prepare()
    has stat'ed the file in the executor. If the file was deleted between the
    preflight existence check and preparation, prepare() converts the response
    to a 404/403 before _start() runs, so the error response goes out without
    a cache header and clients never cache it.
    """

    @override
    async def _start(self, request: BaseRequest) -> AbstractStreamWriter:
        if self.status < 400:
            self.headers[CACHE_CONTROL] = CACHE_HEADER
        return await super()._start(request)


class CachingStaticResource(StaticResource):
    """Static Resource handler that will add cache headers."""

    @override
    async def _handle(self, request: Request) -> StreamResponse:
        """Wrap base handler to cache file path resolution and content type guess."""
        rel_url = request.match_info["filename"]
        key = (rel_url, self._directory)
        hass = request.app[KEY_HASS]
        response: StreamResponse

        if key in RESPONSE_CACHE:
            file_path, content_type = RESPONSE_CACHE[key]
            if not await hass.async_add_executor_job(file_path.is_file):
                # The cached file was deleted after it was cached. Forget the
                # stale entry and resolve again below so the resulting 404
                # goes out without a cache header. pop() is used instead of
                # del so concurrent requests racing to invalidate the same
                # entry don't trip over each other with a KeyError.
                RESPONSE_CACHE.pop(key, None)
            else:
                response = _CacheableFileResponse(
                    file_path, chunk_size=self._chunk_size
                )
                response.headers[CONTENT_TYPE] = content_type
                return response

        response = await super()._handle(request)
        if not isinstance(response, FileResponse):
            # Must be directory index; ignore caching
            return response
        file_path = response._path  # noqa: SLF001
        if not await hass.async_add_executor_job(file_path.is_file):
            # The file does not exist; FileResponse.prepare() will answer
            # with a 404. Don't learn the miss and don't set a cache
            # header, otherwise clients cache the 404 (browsers honor
            # max-age on error responses too).
            return response
        # Build our own response so the cache header is attached from the
        # successful preparation path instead of up front: if the file is
        # deleted after this check, prepare() answers 404 and _start() skips
        # the header for the error status.
        response = _CacheableFileResponse(file_path, chunk_size=self._chunk_size)
        response.content_type = _GUESSER(file_path)[0] or FALLBACK_CONTENT_TYPE
        # Cache actual header after setter construction.
        content_type = response.headers[CONTENT_TYPE]
        RESPONSE_CACHE[key] = (file_path, content_type)
        return response
