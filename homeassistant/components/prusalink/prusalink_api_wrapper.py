from aiohttp import ClientSession

from pyprusalink import PrusaLink as PyPrusaLink, PrinterInfo, JobInfo


class PrusaLink:

    def __init__(self, session: ClientSession, host: str, api_key: str, is_legacy: bool = False):
        self.host = host
        self.is_legacy = is_legacy
        self.api = PyPrusaLink(session, host, api_key)

    async def get_printer(self) -> PrinterInfo:
        return await self.api.get_printer()

    async def get_job(self) -> JobInfo:
        return await self.api.get_job()

    async def get_large_thumbnail(self, path: str) -> bytes:
        if self.is_legacy:
            """Get a large thumbnail."""
            async with self.api.request("GET", f"api/thumbnails{path}.orig.png") as response:
                return await response.read()
        else:
            return await self.api.get_large_thumbnail(path)

    async def cancel_job(self) -> None:
        await self.api.cancel_job()

    async def resume_job(self) -> None:
        await self.api.resume_job()

    async def pause_job(self) -> None:
        await self.api.pause_job()
