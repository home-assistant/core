"""Authentication support for the Hydrawise v2 GraphQL API."""

from datetime import datetime, timedelta
from threading import Lock

import aiohttp

from .exceptions import NotAuthorizedError

CLIENT_ID = "hydrawise_app"
CLIENT_SECRET = "zn3CrjglwNV1"
TOKEN_URL = "https://app.hydrawise.com/api/v2/oauth/access-token"
DEFAULT_TIMEOUT = 60


class Auth:
    """Authentication support for the Hydrawise GraphQL API."""

    def __init__(self, username: str, password: str) -> None:
        """Initialize.

        :param username: The username to use for authenticating with the Hydrawise service.
        :param password: The password to use for authenticating with the Hydrawise service.
        """
        self.__username = username
        self.__password = password
        self._lock = Lock()
        self._token: str | None = None
        self._token_type: str | None = None
        self._token_expires: datetime | None = None
        self._refresh_token: str | None = None

    async def _fetch_token_locked(self, refresh=False):
        data = {
            "client_id": CLIENT_ID,
            "client_secret": CLIENT_SECRET,
        }
        if refresh:
            assert self._token is not None
            data["grant_type"] = "refresh_token"
            data["refresh_token"] = self._refresh_token
        else:
            data["grant_type"] = "password"
            data["scope"] = "all"
            data["username"] = self.__username
            data["password"] = self.__password
        async with aiohttp.ClientSession() as session:
            async with session.post(
                TOKEN_URL,
                headers={"Content-Type": "application/x-www-form-urlencoded"},
                data=data,
                timeout=DEFAULT_TIMEOUT,
            ) as resp:
                resp_json = await resp.json()
                if "error" in resp_json:
                    self._token_type = None
                    self._token = None
                    self._token_expires = None
                    raise NotAuthorizedError(resp_json["message"])
                self._token = resp_json["access_token"]
                self._refresh_token = resp_json["refresh_token"]
                self._token_type = resp_json["token_type"]
                self._token_expires = datetime.now() + timedelta(
                    seconds=resp_json["expires_in"]
                )

    async def check_token(self):
        """Check a token and refresh if necessary."""
        with self._lock:
            if self._token is None:
                await self._fetch_token_locked(refresh=False)
            elif self._token_expires - datetime.now() < timedelta(minutes=5):
                await self._fetch_token_locked(refresh=True)

    async def token(self) -> str:
        """Retrieve an authentication token for the current user.

        :rtype: string
        """
        await self.check_token()
        with self._lock:
            return f"{self._token_type} {self._token}"
