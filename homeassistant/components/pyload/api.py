"""Simple wrapper for pyLoad's API."""

from http import HTTPStatus
from json import JSONDecodeError
import logging
import traceback
from typing import Optional

import aiohttp

_LOGGER = logging.getLogger(__name__)


class PyLoadAPI:
    """Simple wrapper for pyLoad's API."""

    def __init__(
        self,
        session: aiohttp.ClientSession,
        api_url: str,
        username: Optional[str] = None,
        password: Optional[str] = None,
    ) -> None:
        """Initialize pyLoad API."""
        self._session = session
        self.api_url = api_url
        self.status = None
        self.username = username
        self.password = password

    async def login(self):
        """Login to pyLoad API."""

        user_data = {"username": self.username, "password": self.password}
        url = f"{self.api_url}api/login"
        try:
            async with self._session.post(url, data=user_data) as r:
                _LOGGER.debug(
                    "Response from %s [%s]: %s", url, r.status, (await r.text())
                )
                r.raise_for_status()
                try:
                    r = await r.json()
                    if not r:
                        raise InvalidAuth
                except JSONDecodeError:
                    _LOGGER.error(
                        "Exception: Cannot parse login response:\n %s",
                        traceback.format_exc(),
                    )
                else:
                    return r
        except (TimeoutError, aiohttp.ClientError) as e:
            _LOGGER.error("Exception: Cannot login:\n %s", traceback.format_exc())
            raise CannotConnect from e

    async def get_status(self):
        """Get general status information of pyLoad."""
        url = f"{self.api_url}api/statusServer"
        try:
            async with self._session.get(url) as r:
                _LOGGER.debug(
                    "Response from %s [%s]: %s", url, r.status, (await r.text())
                )
                if r.status == HTTPStatus.UNAUTHORIZED:
                    raise InvalidAuth
                try:
                    return await r.json()
                except JSONDecodeError:
                    _LOGGER.error(
                        "Exception: Cannot parse status response:\n %s",
                        traceback.format_exc(),
                    )
                r.raise_for_status()
        except (TimeoutError, aiohttp.ClientError) as e:
            _LOGGER.error("Exception: Cannot get status:\n %s", traceback.format_exc())
            raise CannotConnect("Get status failed due to request exception") from e

    async def version(self):
        """Get version of pyLoad."""
        url = f"{self.api_url}api/getServerVersion"
        try:
            async with self._session.get(url) as r:
                _LOGGER.debug(
                    "Response from %s [%s]: %s", url, r.status, (await r.text())
                )
                if r.status == HTTPStatus.UNAUTHORIZED:
                    raise InvalidAuth
                r.raise_for_status()
                try:
                    return await r.json()
                except JSONDecodeError:
                    _LOGGER.error(
                        "Exception: Cannot parse status response:\n %s",
                        traceback.format_exc(),
                    )
        except (TimeoutError, aiohttp.ClientError) as e:
            _LOGGER.error("Exception: Cannot get version:\n %s", traceback.format_exc())
            raise CannotConnect("Get version failed due to request exception") from e


class CannotConnect(Exception):
    """Error to indicate we cannot connect."""


class InvalidAuth(Exception):
    """Error to indicate there is invalid auth."""
