"""Sanix API class."""
from http import HTTPStatus

import aiohttp

from .const import SANIX_API_HOST


class SanixException(Exception):
    """Raised when Sanix API ended with error."""

    def __init__(self, status_code, status):
        """Initialize the Sanix Exception."""
        self.status_code = status_code
        self.status = status


class Sanix:
    """Sanix API."""

    def __init__(self, serial_no, token, session: aiohttp.ClientSession) -> None:
        """Initialize the class instance."""
        self._serial_no = serial_no
        self._token = token
        self._session = session

    async def fetch_data(self):
        """Fetch the update."""
        _url = f"{SANIX_API_HOST}/api/measurement/read.php?serial_no={self._serial_no}&auth_token={self._token}"

        async with self._session.get(_url) as resp:
            try:
                _json = await resp.json()
            except Exception as err:
                raise SanixException(
                    HTTPStatus.BAD_REQUEST, "Something went wrong"
                ) from err

            _message = _json.get("message")
            if _message and _message == "Brak autoryzacji!":
                raise SanixException(HTTPStatus.UNAUTHORIZED, "Could not authorize.")

            return _json
