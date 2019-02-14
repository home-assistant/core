"""Static file handling for HTTP component."""
from aiohttp import hdrs
from aiohttp.web import FileResponse
from aiohttp.web_exceptions import HTTPNotFound
from aiohttp.web_urldispatcher import StaticResource
from yarl import URL

CACHE_TIME = 31 * 86400  # = 1 month
CACHE_HEADERS = {hdrs.CACHE_CONTROL: "public, max-age={}".format(CACHE_TIME)}


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
        if filepath.is_file():
            return FileResponse(
                filepath, chunk_size=self._chunk_size, headers=CACHE_HEADERS)
        raise HTTPNotFound
