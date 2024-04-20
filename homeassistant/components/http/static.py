"""Static file handling for HTTP component."""

from __future__ import annotations

from collections.abc import Mapping
import mimetypes
from pathlib import Path
from typing import Final

from aiohttp import hdrs
from aiohttp.web import FileResponse, Request, StreamResponse
from aiohttp.web_exceptions import HTTPForbidden, HTTPNotFound
from aiohttp.web_urldispatcher import StaticResource
from lru import LRU

from .const import KEY_HASS

CACHE_TIME: Final = 31 * 86400  # = 1 month
CACHE_HEADER = f"public, max-age={CACHE_TIME}"
CACHE_HEADERS: Mapping[str, str] = {hdrs.CACHE_CONTROL: CACHE_HEADER}
PATH_CACHE: LRU[tuple[str, Path], tuple[Path | None, str | None]] = LRU(512)


def _get_file_path(rel_url: str, directory: Path) -> Path | None:
    """Return the path to file on disk or None."""
    filename = Path(rel_url)
    if filename.anchor:
        # rel_url is an absolute name like
        # /static/\\machine_name\c$ or /static/D:\path
        # where the static dir is totally different
        raise HTTPForbidden
    filepath: Path = directory.joinpath(filename).resolve()
    filepath.relative_to(directory)
    # on opening a dir, load its contents if allowed
    if filepath.is_dir():
        return None
    if filepath.is_file():
        return filepath
    raise FileNotFoundError


class CachingStaticResource(StaticResource):
    """Static Resource handler that will add cache headers."""

    async def _handle(self, request: Request) -> StreamResponse:
        """Return requested file from disk as a FileResponse."""
        rel_url = request.match_info["filename"]
        key = (rel_url, self._directory)
        if (filepath_content_type := PATH_CACHE.get(key)) is None:
            hass = request.app[KEY_HASS]
            try:
                filepath = await hass.async_add_executor_job(_get_file_path, *key)
            except (ValueError, FileNotFoundError) as error:
                # relatively safe
                raise HTTPNotFound from error
            except HTTPForbidden:
                # forbidden
                raise
            except Exception as error:
                # perm error or other kind!
                request.app.logger.exception("Unexpected exception")
                raise HTTPNotFound from error

            content_type: str | None = None
            if filepath is not None:
                content_type = (mimetypes.guess_type(rel_url))[
                    0
                ] or "application/octet-stream"
            PATH_CACHE[key] = (filepath, content_type)
        else:
            filepath, content_type = filepath_content_type

        if filepath and content_type:
            return FileResponse(
                filepath,
                chunk_size=self._chunk_size,
                headers={
                    hdrs.CACHE_CONTROL: CACHE_HEADER,
                    hdrs.CONTENT_TYPE: content_type,
                },
            )

        return await super()._handle(request)
