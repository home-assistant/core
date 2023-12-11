"""hottub contains the Device class that represents an Arctic Spa Hot Tub."""
from hashlib import sha256
from http import HTTPStatus
from urllib.error import HTTPError

from pyarcticspas import Spa


class Device:
    """Device is an Arctic Spa Hot Tub identified by its API key."""

    def __init__(self, api_key: str) -> None:
        """Initialize Spa Entry."""
        self.api = Spa(api_key)
        self.id = sha256(bytes(api_key, "utf8")).hexdigest()

    def authenticate(self) -> int:
        """Authenticate the API key."""
        try:
            self.api.status()
        except HTTPError as e:
            return e.code
        return HTTPStatus.OK

    async def async_authenticate(self) -> int:
        """Authenticate the API key."""
        try:
            await self.api.async_status()
        except HTTPError as e:
            return e.code
        return HTTPStatus.OK
