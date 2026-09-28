"""Read responses without trusting the size they claim."""

from collections.abc import Mapping

from aiohttp import ClientResponse

from ..const import DOWNLOAD_CHUNK_SIZE, MAX_DOWNLOAD_SIZE
from ..exceptions import MarketplaceError


def _declared_size(headers: Mapping[str, str]) -> int:
    """Return the size a response declares, 0 when it declares none."""
    length = headers.get("Content-Length", "")
    return int(length) if length.isdigit() else 0


async def async_read_limited(response: ClientResponse, url: str) -> bytes:
    """Read a response body, giving up as soon as it passes the download limit.

    Without a Content-Length only the bytes that arrive tell the size, so the
    body is read in chunks instead of all at once.
    """
    if _declared_size(response.headers) > MAX_DOWNLOAD_SIZE:
        raise MarketplaceError(
            f"{url} declares more than the {MAX_DOWNLOAD_SIZE} byte limit"
        )

    content = bytearray()
    async for chunk in response.content.iter_chunked(DOWNLOAD_CHUNK_SIZE):
        content.extend(chunk)
        if len(content) > MAX_DOWNLOAD_SIZE:
            raise MarketplaceError(
                f"{url} is larger than the {MAX_DOWNLOAD_SIZE} byte limit"
            )

    return bytes(content)
