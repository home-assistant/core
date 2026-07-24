"""Provides a wrapper for interacting with the MAWAQIT API.

It includes functions for testing credentials, retrieving API tokens,
fetching prayer times, and finding mosques in the neighborhood.
"""

import logging
from typing import cast

from aiohttp import ClientSession
from mawaqit import AsyncMawaqitClient
from mawaqit.exceptions import BadCredentialsException, MawaqitException

from .types import MawaqitMosqueData

_LOGGER = logging.getLogger(__name__)


async def validate_credentials(
    username: str | None = None,
    password: str | None = None,
    session: ClientSession | None = None,
    client_instance: AsyncMawaqitClient | None = None,
) -> bool:
    """Return True if the MAWAQIT credentials is valid."""
    try:
        client = client_instance
        if client is None:
            client = AsyncMawaqitClient(
                username=username, password=password, session=session
            )
        await client.login()
    except BadCredentialsException:
        return False
    except MawaqitException as e:
        _LOGGER.debug("Mawaqit error validating credentials: %s", e)
        raise
    finally:
        if client is not None:
            await client.close()

    return True


async def get_mawaqit_api_token(
    username: str | None = None,
    password: str | None = None,
    session: ClientSession | None = None,
    client_instance: AsyncMawaqitClient | None = None,
) -> str | None:
    """Return the MAWAQIT API token."""
    token = None
    try:
        client = client_instance
        if client is None:
            client = AsyncMawaqitClient(
                username=username, password=password, session=session
            )
        token = await client.get_api_token()
    except BadCredentialsException as e:
        _LOGGER.debug("Error on retrieving API Token: %s", e)
    except MawaqitException as e:
        _LOGGER.debug("Mawaqit error on retrieving API Token: %s", e)
    except (ConnectionError, TimeoutError) as e:
        _LOGGER.debug("Network-related error: %s", e)
    finally:
        if client is not None:
            await client.close()
    return token


async def all_mosques_neighborhood(
    latitude: float,
    longitude: float,
    mosque: str | None = None,
    username: str | None = None,
    password: str | None = None,
    token: str | None = None,
    session: ClientSession | None = None,
    client_instance: AsyncMawaqitClient | None = None,
) -> list[MawaqitMosqueData] | None:
    """Return mosques in the neighborhood if any. Returns a list of dicts."""
    client = client_instance
    try:
        if client is None:
            client = AsyncMawaqitClient(
                latitude, longitude, mosque, username, password, token, session=session
            )
        await client.get_api_token()

        response = await client.all_mosques_neighborhood()
        return [MawaqitMosqueData.from_dict(mosque) for mosque in response]
    finally:
        if client is not None:
            await client.close()


async def all_mosques_by_keyword(
    search_keyword: str | None,
    page: int = 1,
    username: str | None = None,
    password: str | None = None,
    token: str | None = None,
    session: ClientSession | None = None,
    client_instance: AsyncMawaqitClient | None = None,
) -> list[MawaqitMosqueData]:
    """Return mosques matching the keyword. Returns a list of dicts."""
    client = client_instance
    try:
        if client is None:
            client = AsyncMawaqitClient(
                username=username, password=password, token=token, session=session
            )
        await client.get_api_token()

        if search_keyword is not None:
            response = await client.fetch_mosques_by_keyword(search_keyword, page=page)
            return [MawaqitMosqueData.from_dict(mosque) for mosque in response]
        return []
    finally:
        if client is not None:
            await client.close()


async def fetch_prayer_times(
    latitude: float | None = None,
    longitude: float | None = None,
    mosque: str | None = None,
    username: str | None = None,
    password: str | None = None,
    token: str | None = None,
    session: ClientSession | None = None,
    client_instance: AsyncMawaqitClient | None = None,
) -> dict | None:
    """Get prayer times from the MAWAQIT API. Returns a dict."""
    client = client_instance
    try:
        if client is None:
            client = AsyncMawaqitClient(
                latitude, longitude, mosque, username, password, token, session=session
            )
        await client.get_api_token()
        return cast("dict | None", await client.fetch_prayer_times())
    finally:
        if client is not None:
            await client.close()


async def fetch_mosque_by_id(
    mosque: str,
    token: str | None = None,
    session: ClientSession | None = None,
    client_instance: AsyncMawaqitClient | None = None,
) -> dict | None:
    """Get Mosque data by ID from the MAWAQIT API. Returns a dict."""
    client = client_instance
    try:
        if client is None:
            client = AsyncMawaqitClient(token=token, session=session)
        await client.get_api_token()
        return cast("dict | None", await client.fetch_mosque_by_id(mosque))
    finally:
        if client is not None:
            await client.close()
