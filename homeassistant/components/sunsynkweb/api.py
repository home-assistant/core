"""stub for api access functions not attached to objects."""

import logging
import pprint

from .const import BASE_HEADERS, BASE_URL

_LOGGER = logging.getLogger(__name__)


async def get_bearer_token(session, username, password):
    """Get the bearer token for the sunsynk api."""
    params = {
        "username": username,
        "password": password,
        "grant_type": "password",
        "client_id": "csp-web",
        "source": "sunsynk",
        "areaCode": "sunsynk",
    }
    returned = await session.post(
        BASE_URL + "/oauth/token", json=params, headers=BASE_HEADERS
    )

    returned = await returned.json()
    _LOGGER.debug("authentication attempt returned %s", pprint.pformat(returned))
    # returned data looks like the below
    # {
    #     "code": 0,
    #     "msg": "Success",
    #     "data": {
    #         "access_token": "VALUE",
    #         "token_type": "bearer",
    #         "refresh_token": "VALUE",
    #         "expires_in": 604799,
    #         "scope": "all",
    #     },
    #     "success": True,
    # }
    return returned["data"]["access_token"]
