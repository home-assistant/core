"""Static file handling for HTTP component."""
from pathlib import Path

from aiohttp import hdrs
from aiohttp.web import FileResponse
from aiohttp.web_exceptions import HTTPNotFound, HTTPForbidden
from aiohttp.web_urldispatcher import StaticResource

CACHE_TIME = 31 * 86400  # = 1 month
CACHE_HEADERS = {hdrs.CACHE_CONTROL: "public, max-age={}".format(CACHE_TIME)}


# https://github.com/PyCQA/astroid/issues/633
# pylint: disable=duplicate-bases
class CachingStaticResource(StaticResource):
    """Static Resource handler that will add cache headers."""

    async def _handle(self, request):
        rel_url = request.match_info['filename']
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
                filepath, chunk_size=self._chunk_size, headers=CACHE_HEADERS)
        raise HTTPNotFound
