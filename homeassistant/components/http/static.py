"""Static file handling for HTTP component."""

from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path
from typing import Final

from aiohttp.hdrs import CACHE_CONTROL
from aiohttp.web import FileResponse, Request, StreamResponse
from aiohttp.web_fileresponse import CONTENT_TYPES, FALLBACK_CONTENT_TYPE
from aiohttp.web_urldispatcher import StaticResource
from lru import LRU

CACHE_TIME: Final = 31 * 86400  # = 1 month
CACHE_HEADER = f"public, max-age={CACHE_TIME}"
CACHE_HEADERS: Mapping[str, str] = {CACHE_CONTROL: CACHE_HEADER}
RESPONSE_CACHE: LRU[tuple[str, Path], tuple[Path, str]] = LRU(512)


class CachingStaticResource(StaticResource):
    """Static Resource handler that will add cache headers."""

    async def _handle(self, request: Request) -> StreamResponse:
        """Wrap base handler to cache file path resolution and content type guess."""
        rel_url = request.match_info["filename"]
        key = (rel_url, self._directory)
        response: StreamResponse

        if cached_values := RESPONSE_CACHE.get(key):
            file_path, content_type = cached_values
            response = FileResponse(file_path, chunk_size=self._chunk_size)
        else:
            response = await super()._handle(request)
            if not isinstance(response, FileResponse):
                # Must be directory index; ignore caching
                return response
            file_path = response._path  # noqa: SLF001
            content_type = (
                CONTENT_TYPES.guess_type(file_path)[0] or FALLBACK_CONTENT_TYPE
            )
            RESPONSE_CACHE[key] = (file_path, content_type)

        response.headers[CACHE_CONTROL] = CACHE_HEADER
        response.content_type = content_type
        return response
