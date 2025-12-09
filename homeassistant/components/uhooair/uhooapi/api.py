"""Imports for api.py."""

import logging

from aiohttp import ClientError, ClientResponseError, ClientSession
from aiohttp.hdrs import AUTHORIZATION

from ..const import LOGGER
from .endpoints import API_URL_BASE, DEVICE_DATA, DEVICE_LIST, GENERATE_TOKEN
from .errors import ForbiddenError, RequestError, UnauthorizedError
from .util import json_pp


class API:
    """API Class Object for Uhoo API."""

    def __init__(self, websession: ClientSession) -> None:
        """Initialize API class."""
        self._log: logging.Logger = LOGGER
        self._websession: ClientSession = websession
        self._bearer_token: str | None = None

    async def _request(
        self, method: str, scaffold: str, endpoint: str, data: dict | None = None
    ):
        headers = {}
        if self._bearer_token:
            headers.update({AUTHORIZATION: f"Bearer {self._bearer_token}"})

        self._log.debug(f"[_request] {method} {scaffold}/{endpoint}")

        if method.lower() == "post":
            self._log.debug(f"[_request] {json_pp(data)}")

        async with self._websession.request(
            method, f"{scaffold}/{endpoint}", headers=headers, data=data
        ) as resp:
            json = None
            text = None
            try:
                self._log.debug(
                    f"[_request] {resp.status} {method} {scaffold}/{endpoint}"
                )
                if resp.content_type == "application/json":
                    json = await resp.json()
                else:
                    text = await resp.text()
                resp.raise_for_status()
            except ClientResponseError as err:
                if err.status == 401:
                    self._log.debug(
                        f"[_request] 401 Unauthorized:\n{json_pp(json) or text}"
                    )
                    raise UnauthorizedError(json_pp(json)) from None
                if err.status == 403:
                    self._log.debug(
                        f"[_request] 403 Unauthorized:\n{text or json_pp(json)}"
                    )
                    raise ForbiddenError(text or json or "No error details") from None
                raise RequestError(
                    f"Error requesting data from {scaffold}/{endpoint}: {err}"
                ) from None
            except ClientError as err:
                raise RequestError(
                    f"Error requesting data from {scaffold}/{endpoint}: {err}"
                ) from None
            else:
                return json

    def set_bearer_token(self, bearer_token: str | None) -> None:
        """Setting the bearer token for API."""
        self._bearer_token = bearer_token

    async def generate_token(self, api_key: str) -> dict | None:
        """Generating the bearer token for API."""
        resp: dict | None = await self._request(
            "post", API_URL_BASE, GENERATE_TOKEN, data={"code": api_key}
        )
        return resp

    async def get_device_data(
        self, serial_number: str, mode: str, limit: int
    ) -> dict | None:
        """Get Device Data from Uhoo API."""
        resp: dict | None = await self._request(
            "post",
            API_URL_BASE,
            DEVICE_DATA,
            data={"serialNumber": serial_number, "mode": mode, "limit": limit},
        )
        return resp

    async def get_device_list(self) -> list | None:
        """Get list of devices from Uhoo API."""
        resp: list | None = await self._request("post", API_URL_BASE, DEVICE_LIST)
        return resp
