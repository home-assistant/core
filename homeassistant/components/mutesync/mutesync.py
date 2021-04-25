from functools import partial
import json
import logging
from typing import Dict

import aiohttp
import async_timeout

_LOGGER = logging.getLogger(__name__)


async def authenticate(session: aiohttp.ClientSession, host: str) -> str:
    """Authenticate and return a token."""
    with async_timeout.timeout(10):
        resp = await session.request(
            "get",
            "http://" + host + ":8249/authenticate",
            data={},
            raise_for_status=True,
        )

    data = await resp.json()
    return data["token"]


class PyMutesync:
    def __init__(self, token, host, session: aiohttp.ClientSession):
        self.token = token
        self.host = host
        self.session = session

    async def request(self, method, path, data=None) -> Dict:
        url = f"http://{self.host}:8249/{path}"
        kwargs = {}
        if data:
            if method == "get":
                kwargs["query"] = data
            else:
                kwargs["json"] = data
        with async_timeout.timeout(10):
            resp = await self.session.request(
                method,
                url,
                headers={
                    "Authorization": f"Token {self.token}",
                    "x-mutesync-api-version": "1",
                },
                raise_for_status=True,
                **kwargs,
            )
        response = await resp.json()
        return response["data"]

    async def get_state(self):
        return await self.request("get", "state")
