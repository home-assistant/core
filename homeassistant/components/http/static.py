"""Static file handling for HTTP component."""
from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path
from typing import Final

from aiohttp import hdrs
from aiohttp.web import FileResponse, Request, StreamResponse
from aiohttp.web_exceptions import HTTPForbidden, HTTPNotFound
from aiohttp.web_urldispatcher import StaticResource

CACHE_TIME: Final = 31 * 86400  # = 1 month
CACHE_HEADERS: Final[Mapping[str, str]] = {
    hdrs.CACHE_CONTROL: f"public, max-age={CACHE_TIME}"
}


class CachingStaticResource(StaticResource):
    """Static Resource handler that will add cache headers."""

    async def _handle(self, request: Request) -> StreamResponse:
        rel_url = request.match_info["filename"]
        try:
            filename = Path(rel_url)
            if filename.anchor:
                # rel_url is an absolute name like
                # /static/\\machine_name\c$ or /static/D:\path
                # where the static dir is totally different
                raise HTTPForbidden()
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

        # on opening a dir, load its contents if allowed
        if filepath.is_dir():
            return await super()._handle(request)
        if filepath.is_file():
            return FileResponse(
                filepath,
                chunk_size=self._chunk_size,
                headers=CACHE_HEADERS,
            )
        raise HTTPNotFound
