"""Static file handling for HTTP component."""

from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path
import sys
from typing import Final

from aiohttp.hdrs import CACHE_CONTROL, CONTENT_TYPE
from aiohttp.web import FileResponse, Request, StreamResponse
from aiohttp.web_fileresponse import CONTENT_TYPES, FALLBACK_CONTENT_TYPE
from aiohttp.web_urldispatcher import StaticResource
from lru import LRU

CACHE_TIME: Final = 31 * 86400  # = 1 month
CACHE_HEADER = f"public, max-age={CACHE_TIME}"
CACHE_HEADERS: Mapping[str, str] = {CACHE_CONTROL: CACHE_HEADER}
RESPONSE_CACHE: LRU[tuple[str, Path], tuple[Path, str]] = LRU(512)

if sys.version_info >= (3, 13):
    # guess_type is soft-deprecated in 3.13
    # for paths and should only be used for
    # URLs. guess_file_type should be used
    # for paths instead.
    _GUESSER = CONTENT_TYPES.guess_file_type
else:
    _GUESSER = CONTENT_TYPES.guess_type


class CachingStaticResource(StaticResource):
    """Static Resource handler that will add cache headers."""

    async def _handle(self, request: Request) -> StreamResponse:
        """Wrap base handler to cache file path resolution and content type guess."""
        rel_url = request.match_info["filename"]
        key = (rel_url, self._directory)
        response: StreamResponse

        if key in RESPONSE_CACHE:
            file_path, content_type = RESPONSE_CACHE[key]
            response = FileResponse(file_path, chunk_size=self._chunk_size)
            response.headers[CONTENT_TYPE] = content_type
        else:
            response = await super()._handle(request)
            if not isinstance(response, FileResponse):
                # Must be directory index; ignore caching
                return response
            file_path = response._path  # noqa: SLF001
            response.content_type = _GUESSER(file_path)[0] or FALLBACK_CONTENT_TYPE
            # Cache actual header after setter construction.
            content_type = response.headers[CONTENT_TYPE]
            RESPONSE_CACHE[key] = (file_path, content_type)

        response.headers[CACHE_CONTROL] = CACHE_HEADER
        return response
