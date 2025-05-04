"""Provides a wrapper for interacting with the MAWAQIT API.

It includes functions for testing credentials, retrieving API tokens,
fetching prayer times, and finding mosques in the neighborhood.
"""

import logging

from mawaqit import AsyncMawaqitClient
from mawaqit.consts import BadCredentialsException

_LOGGER = logging.getLogger(__name__)


async def test_credentials(username=None, password=None, client_instance=None):
    """Return True if the MAWAQIT credentials is valid."""
    try:
        client = client_instance
        if client is None:
            client = AsyncMawaqitClient(username=username, password=password)
        await client.login()
    except BadCredentialsException:
        _LOGGER.error("Error : Bad Credentials")
        return False
    except (ConnectionError, TimeoutError) as e:
        _LOGGER.error("Network-related error: %s", e)
    finally:
        if client is not None:
            await client.close()

    return True


async def get_mawaqit_api_token(username=None, password=None, client_instance=None):
    """Return the MAWAQIT API token."""
    token = None
    try:
        client = client_instance
        if client is None:
            client = AsyncMawaqitClient(username=username, password=password)
        token = await client.get_api_token()
    except BadCredentialsException as e:
        _LOGGER.error("Error on retrieving API Token: %s", e)
    except (ConnectionError, TimeoutError) as e:
        _LOGGER.error("Network-related error: %s", e)
    finally:
        if client is not None:
            await client.close()
    return token


async def all_mosques_neighborhood(
    latitude,
    longitude,
    mosque=None,
    username=None,
    password=None,
    token=None,
    client_instance=None,
):
    """Return mosques in the neighborhood if any. Returns a list of dicts."""
    nearest_mosques = None
    try:
        client = client_instance
        if client is None:
            client = AsyncMawaqitClient(
                latitude, longitude, mosque, username, password, token, session=None
            )
        else:
            # would be better to set pos in client
            pass
        await client.get_api_token()
        nearest_mosques = await client.all_mosques_neighborhood()
    except BadCredentialsException as e:
        _LOGGER.error("Error on retrieving mosques: %s", e)
    except (ConnectionError, TimeoutError) as e:
        _LOGGER.error("Network-related error: %s", e)
    finally:
        if client is not None:
            await client.close()

    return nearest_mosques


async def all_mosques_by_keyword(
    search_keyword, username=None, password=None, token=None, client_instance=None
):
    """Return mosques in the neighborhood if any. Returns a list of dicts."""
    search_mosques = []
    try:
        client = client_instance
        if client is None:
            client = AsyncMawaqitClient(
                username=username, password=password, token=token, session=None
            )
        else:
            # would be better to set pos in client
            pass
        await client.get_api_token()

        if search_keyword is not None:
            search_mosques = await client.fetch_mosques_by_keyword(search_keyword)

    except BadCredentialsException as e:
        _LOGGER.error("Error on retrieving mosques: %s", e)
    except (ConnectionError, TimeoutError) as e:
        _LOGGER.error("Network-related error: %s", e)
    finally:
        if client is not None:
            await client.close()

    return search_mosques


async def fetch_prayer_times(
    latitude=None,
    longitude=None,
    mosque=None,
    username=None,
    password=None,
    token=None,
    client_instance=None,
):
    """Get prayer times from the MAWAQIT API. Returns a dict."""
    dict_calendar = None
    try:
        client = client_instance
        if client is None:
            client = AsyncMawaqitClient(
                latitude, longitude, mosque, username, password, token, session=None
            )
        else:
            # would be better to set pos in client
            pass
        await client.get_api_token()
        dict_calendar = await client.fetch_prayer_times()

    except BadCredentialsException as e:
        _LOGGER.error("Error on retrieving prayer times: %s", e)
    except (ConnectionError, TimeoutError) as e:
        _LOGGER.error("Network-related error: %s", e)
    finally:
        if client is not None:
            await client.close()

    return dict_calendar
