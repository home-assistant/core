"""Connection manaement."""
import logging

import httpx

LOGGER = logging.getLogger(__name__)


class Connection:
    """Class to manage Connection."""

    def __init__(self, websession: httpx.AsyncClient, host):
        """Initialize Connection Object."""
        self._host = host
        self._websession = websession

    async def get(self, url, username=None, password=None):
        """Do http get request to url."""
        LOGGER.debug("username: %s", username)
        if username is not None:
            auth = httpx.BasicAuth(username, password)

        LOGGER.debug("URL: %s", url)
        try:
            # resp = await getattr(self._websession, method)(
            #     url, headers=headers, params=params, auth=auth
            # )
            resp = await self._websession.get(url, auth=auth)
            return resp
        except httpx.HTTPError as err:
            LOGGER.error("Err: %s", err)
