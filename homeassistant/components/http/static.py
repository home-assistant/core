"""Static file handling for HTTP component."""

from collections.abc import Mapping
from pathlib import Path
from typing import Final, override

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
                # goes out without a cache header.
                del RESPONSE_CACHE[key]
            else:
                response = FileResponse(file_path, chunk_size=self._chunk_size)
                response.headers[CONTENT_TYPE] = content_type
                response.headers[CACHE_CONTROL] = CACHE_HEADER
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
        response.content_type = _GUESSER(file_path)[0] or FALLBACK_CONTENT_TYPE
        # Cache actual header after setter construction.
        content_type = response.headers[CONTENT_TYPE]
        RESPONSE_CACHE[key] = (file_path, content_type)
        response.headers[CACHE_CONTROL] = CACHE_HEADER
        return response
