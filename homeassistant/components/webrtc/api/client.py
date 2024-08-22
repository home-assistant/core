"""Client library for go2rtc."""

from __future__ import annotations

from collections.abc import Mapping
import logging
from typing import Any, Final, Literal
from urllib.parse import urljoin

from aiohttp import ClientError, ClientResponse, ClientSession
from mashumaro.codecs.orjson import ORJSONDecoder

from .models import Stream, WebRTCSdpAnswer, WebRTCSdpOffer

_LOGGER = logging.getLogger(__name__)

_API_PREFIX = "/api"
STREAMS_PATH = _API_PREFIX + "/streams"


class _BaseClient:
    """Base client for go2rtc."""

    def __init__(self, websession: ClientSession, server_url: str) -> None:
        """Initialize Client."""
        self._session = websession
        self._base_url = server_url

    async def request(
        self,
        method: Literal["get", "post", "put", "delete"],
        path: str,
        *,
        params: Mapping[str, Any] | None = None,
        data: Any | None = None,
    ) -> ClientResponse:
        """Make a request to the server."""
        url = self._request_url(path)
        _LOGGER.debug("request[%s] %s", method, url)
        try:
            resp = await self._session.request(method, url, params=params, data=data)
        except ClientError as err:
            raise ClientError(f"Server communication failure: {err}") from err

        return resp

    def _request_url(self, path: str) -> str:
        """Return a request url for the specific path."""
        if not self._base_url:
            return path
        return urljoin(self._base_url, path)


class _WebRTCClient:
    """Client for WebRTC module."""

    path: Final = _API_PREFIX + "/webrtc"

    def __init__(self, client: _BaseClient) -> None:
        """Initialize Client."""
        self._client = client

    async def _forward_sdp_offer(
        self, stream_name: str, offer: WebRTCSdpOffer, src_or_dst: Literal["src", "dst"]
    ) -> WebRTCSdpAnswer:
        """Forward an SDP offer to the server."""
        resp = await self._client.request(
            "post",
            self.path,
            params={src_or_dst: stream_name},
            data=offer.to_json(),
        )
        return WebRTCSdpAnswer.from_json(await resp.text())

    async def forward_whep_sdp_offer(
        self, source_name: str, offer: WebRTCSdpOffer
    ) -> WebRTCSdpAnswer:
        """Forward an WHEP SDP offer to the server."""
        return await self._forward_sdp_offer(
            source_name,
            offer,
            "src",
        )


_GET_STREAMS_DECODER = ORJSONDecoder(dict[str, Stream])


class Go2rtcClient:
    """Client for go2rtc server."""

    def __init__(self, websession: ClientSession, server_url: str) -> None:
        """Initialize Client."""
        self._client = _BaseClient(websession, server_url)
        self.webrtc: Final = _WebRTCClient(self._client)

    async def list_streams(self) -> dict[str, Stream]:
        """List streams registered with the server."""
        resp = await self._client.request("get", STREAMS_PATH)
        resp.raise_for_status()
        return _GET_STREAMS_DECODER.decode(await resp.text())

    async def add_stream(self, name: str, source: str) -> None:
        """Add a stream to the server."""
        resp = await self._client.request(
            "put",
            STREAMS_PATH,
            params={"name": name, "src": source},
        )
        resp.raise_for_status()
