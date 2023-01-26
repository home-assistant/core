"""Static file handling for HTTP component."""
from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path
from typing import Final

from aiohttp import hdrs
from aiohttp.web import FileResponse, Request, StreamResponse
from aiohttp.web_exceptions import HTTPForbidden, HTTPNotFound
from aiohttp.web_urldispatcher import StaticResource
from lru import LRU  # pylint: disable=no-name-in-module

from homeassistant.core import HomeAssistant

from .const import KEY_HASS

CACHE_TIME: Final = 31 * 86400  # = 1 month
CACHE_HEADERS: Final[Mapping[str, str]] = {
    hdrs.CACHE_CONTROL: f"public, max-age={CACHE_TIME}"
}
PATH_CACHE = LRU(512)


def _get_file_path(
    filename: str | Path, directory: Path, follow_symlinks: bool
) -> Path | None:
    filepath = directory.joinpath(filename).resolve()
    if not follow_symlinks:
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
        rel_url = request.match_info["filename"]
        hass: HomeAssistant = request.app[KEY_HASS]
        filename = Path(rel_url)
        if filename.anchor:
            # rel_url is an absolute name like
            # /static/\\machine_name\c$ or /static/D:\path
            # where the static dir is totally different
            raise HTTPForbidden()
        try:
            key = (filename, self._directory, self._follow_symlinks)
            if (filepath := PATH_CACHE.get(key)) is None:
                filepath = PATH_CACHE[key] = await hass.async_add_executor_job(
                    _get_file_path, filename, self._directory, self._follow_symlinks
                )
        except (ValueError, FileNotFoundError) as error:
            # relatively safe
            raise HTTPNotFound() from error
        except Exception as error:
            # perm error or other kind!
            request.app.logger.exception(error)
            raise HTTPNotFound() from error

        if filepath:
            return FileResponse(
                filepath,
                chunk_size=self._chunk_size,
                headers=CACHE_HEADERS,
            )
        return await super()._handle(request)
