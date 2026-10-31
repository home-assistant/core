"""Read responses without trusting the size they claim."""

from collections.abc import Mapping

from aiohttp import ClientResponse

from ..const import DOMAIN, DOWNLOAD_CHUNK_SIZE, MAX_DOWNLOAD_SIZE
from ..exceptions import MarketplaceError


def _declared_size(headers: Mapping[str, str]) -> int:
    """Return the size a response declares, 0 when it declares none."""
    length = headers.get("Content-Length", "")
    return int(length) if length.isdigit() else 0


async def async_read_limited(
    response: ClientResponse, url: str, limit: int | None = None
) -> bytes:
    """Read a response body, giving up as soon as it passes the limit.

    Without a Content-Length only the bytes that arrive tell the size, so the
    body is read in chunks instead of all at once. Without a limit, the
    download limit applies.
    """
    if limit is None:
        limit = MAX_DOWNLOAD_SIZE

    if _declared_size(response.headers) > limit:
        raise MarketplaceError(
            translation_domain=DOMAIN,
            translation_key="download_too_large",
            translation_placeholders={"url": url, "limit": str(limit)},
        )

    content = bytearray()
    async for chunk in response.content.iter_chunked(DOWNLOAD_CHUNK_SIZE):
        content.extend(chunk)
        if len(content) > limit:
            raise MarketplaceError(
                translation_domain=DOMAIN,
                translation_key="download_too_large",
                translation_placeholders={"url": url, "limit": str(limit)},
            )

    return bytes(content)
