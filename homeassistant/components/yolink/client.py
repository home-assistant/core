"""Client of YoLink API."""

from typing import Any, Dict

from aiohttp.client import ClientResponse

from .api import AuthenticationManager
from .const import YOLINK_API_GATE
from .model import BRDP


class YoLinkHttpClient:
    """YoLink API Client."""

    def __init__(self, auth: AuthenticationManager):
        """Initialize the YoLink API."""
        self._auth_mgr = auth

    async def request(
        self,
        method: str,
        url: str,
        include_auth: bool = True,
        **kwargs: Any,
    ) -> ClientResponse:
        """Proxy Request and add Auth/CV headers."""
        headers = kwargs.pop("headers", {})
        params = kwargs.pop("params", None)
        data = kwargs.pop("data", None)

        # Extra, user supplied values
        extra_headers = kwargs.pop("extra_headers", None)
        extra_params = kwargs.pop("extra_params", None)
        extra_data = kwargs.pop("extra_data", None)
        if include_auth:
            # Ensure tokens valid
            await self._auth_mgr.check_and_refresh_token()
            # Set auth header
            headers["Authorization"] = self._auth_mgr.httpAuthHeader()
        # Extend with optionally supplied values
        if extra_headers:
            headers.update(extra_headers)
        if extra_params:
            # query parameters
            params = params or {}
            params.update(extra_params)
        if extra_data:
            # form encoded post data
            data = data or {}
            data.update(extra_data)
        return await self._auth_mgr.httpClientSession.request(
            method, url, **kwargs, headers=headers, params=params, data=data, timeout=8
        )

    async def get(self, url: str, **kwargs: Any) -> ClientResponse:
        """Call YoLink API with GET."""
        return await self.request("GET", url, True, **kwargs)

    async def post(self, url: str, **kwargs: Any) -> ClientResponse:
        """Call YoLink API with POST."""
        return await self.request("POST", url, True, **kwargs)

    async def callYoLinkAPI(self, bsdp: Dict, **kwargs: Any) -> BRDP:
        """Call YoLink API with BSDP."""
        resp = await self.post(YOLINK_API_GATE, json=bsdp, **kwargs)
        resp.raise_for_status()
        brdp = BRDP.parse_raw(await resp.text())
        brdp.raise_for_status()
        return brdp

    async def getDeviceList(self, **kwargs: Any) -> BRDP:
        """Call YoLink API -> Manage.getDeviceList."""
        return await self.callYoLinkAPI({"method": "Manage.getDeviceList"}, **kwargs)
