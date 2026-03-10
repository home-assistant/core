"""Helpers for Duck DNS integration."""

from aiohttp import ClientSession

from homeassistant.helpers.typing import UNDEFINED, UndefinedType

UPDATE_URL = "https://www.duckdns.org/update"


async def update_duckdns(
    session: ClientSession,
    domain: str,
    token: str,
    *,
    txt: str | None | UndefinedType = UNDEFINED,
    clear: bool = False,
) -> bool:
    """Update DuckDNS."""
    params = {"domains": domain, "token": token}

    if txt is not UNDEFINED:
        if txt is None:
            # Pass in empty txt value to indicate it's clearing txt record
            params["txt"] = ""
            clear = True
        else:
            params["txt"] = txt

    if clear:
        params["clear"] = "true"

    resp = await session.get(UPDATE_URL, params=params)
    body = await resp.text()

    return body == "OK"
