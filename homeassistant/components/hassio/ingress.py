"""Hass.io Add-on ingress service."""

from __future__ import annotations

import asyncio
from collections.abc import Iterable
from functools import lru_cache
from ipaddress import ip_address
import logging
from urllib.parse import quote

import aiohttp
from aiohttp import ClientTimeout, ClientWebSocketResponse, hdrs, web
from aiohttp.web_exceptions import HTTPBadGateway, HTTPBadRequest
from multidict import CIMultiDict
from yarl import URL

from homeassistant.components.http import HomeAssistantView
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.typing import UNDEFINED
from homeassistant.util.async_ import create_eager_task

from .const import X_HASS_SOURCE, X_INGRESS_PATH
from .http import should_compress

_LOGGER = logging.getLogger(__name__)

INIT_HEADERS_FILTER = {
    hdrs.CONTENT_LENGTH,
    hdrs.CONTENT_ENCODING,
    hdrs.TRANSFER_ENCODING,
    hdrs.ACCEPT_ENCODING,  # Avoid local compression, as we will compress at the border
    hdrs.SEC_WEBSOCKET_EXTENSIONS,
    hdrs.SEC_WEBSOCKET_PROTOCOL,
    hdrs.SEC_WEBSOCKET_VERSION,
    hdrs.SEC_WEBSOCKET_KEY,
}
RESPONSE_HEADERS_FILTER = {
    hdrs.TRANSFER_ENCODING,
    hdrs.CONTENT_LENGTH,
    hdrs.CONTENT_TYPE,
    hdrs.CONTENT_ENCODING,
}

MIN_COMPRESSED_SIZE = 128
MAX_SIMPLE_RESPONSE_SIZE = 4194000

DISABLED_TIMEOUT = ClientTimeout(total=None)


@callback
def async_setup_ingress_view(hass: HomeAssistant, host: str) -> None:
    """Auth setup."""
    websession = async_get_clientsession(hass)

    hassio_ingress = HassIOIngress(host, websession)
    hass.http.register_view(hassio_ingress)


class HassIOIngress(HomeAssistantView):
    """Hass.io view to handle base part."""

    name = "api:hassio:ingress"
    url = "/api/hassio_ingress/{token}/{path:.*}"
    requires_auth = False

    def __init__(self, host: str, websession: aiohttp.ClientSession) -> None:
        """Initialize a Hass.io ingress view."""
        self._host = host
        self._websession = websession
        self._url = URL(f"http://{host}")

    @lru_cache
    def _create_url(self, token: str, path: str) -> URL:
        """Create URL to service."""
        base_path = f"/ingress/{token}/"

        try:
            target_url = self._url.join(URL(f"{base_path}{quote(path)}"))
        except ValueError as err:
            raise HTTPBadRequest from err

        if not target_url.path.startswith(base_path):
            raise HTTPBadRequest

        return target_url

    async def _handle(
        self, request: web.Request, token: str, path: str
    ) -> web.Response | web.StreamResponse | web.WebSocketResponse:
        """Route data to Hass.io ingress service."""
        try:
            # Websocket
            if _is_websocket(request):
                return await self._handle_websocket(request, token, path)

            # Request
            return await self._handle_request(request, token, path)

        except aiohttp.ClientError as err:
            _LOGGER.debug("Ingress error with %s / %s: %s", token, path, err)

        raise HTTPBadGateway from None

    get = _handle
    post = _handle
    put = _handle
    delete = _handle
    options = _handle
    patch = _handle
    connect = _handle
    head = _handle
    trace = _handle

    async def _handle_websocket(
        self, request: web.Request, token: str, path: str
    ) -> web.WebSocketResponse:
        """Ingress route for websocket."""
        req_protocols: Iterable[str]
        if hdrs.SEC_WEBSOCKET_PROTOCOL in request.headers:
            req_protocols = [
                str(proto.strip())
                for proto in request.headers[hdrs.SEC_WEBSOCKET_PROTOCOL].split(",")
            ]
        else:
            req_protocols = ()

        ws_server = web.WebSocketResponse(
            protocols=req_protocols, autoclose=False, autoping=False
        )
        await ws_server.prepare(request)

        # Preparing
        url = self._create_url(token, path)
        source_header = _init_header(request, token)

        # Support GET query
        if request.query_string:
            url = url.with_query(request.query_string)

        # Start proxy
        async with self._websession.ws_connect(
            url,
            headers=source_header,
            protocols=req_protocols,
            autoclose=False,
            autoping=False,
        ) as ws_client:
            # Proxy requests
            await asyncio.wait(
                [
                    create_eager_task(_websocket_forward(ws_server, ws_client)),
                    create_eager_task(_websocket_forward(ws_client, ws_server)),
                ],
                return_when=asyncio.FIRST_COMPLETED,
            )

        return ws_server

    async def _handle_request(
        self, request: web.Request, token: str, path: str
    ) -> web.Response | web.StreamResponse:
        """Ingress route for request."""
        url = self._create_url(token, path)
        source_header = _init_header(request, token)

        async with self._websession.request(
            request.method,
            url,
            headers=source_header,
            params=request.query,
            allow_redirects=False,
            data=request.content if request.method != "GET" else None,
            timeout=DISABLED_TIMEOUT,
            skip_auto_headers={hdrs.CONTENT_TYPE},
        ) as result:
            headers = _response_header(result)
            content_length_int = 0
            content_length = result.headers.get(hdrs.CONTENT_LENGTH, UNDEFINED)
            # Avoid parsing content_type in simple cases for better performance
            if maybe_content_type := result.headers.get(hdrs.CONTENT_TYPE):
                content_type: str = (maybe_content_type.partition(";"))[0].strip()
            else:
                # default value according to RFC 2616
                content_type = "application/octet-stream"

            # Simple request
            if result.status in (204, 304) or (
                content_length is not UNDEFINED
                and (content_length_int := int(content_length))
                <= MAX_SIMPLE_RESPONSE_SIZE
            ):
                # Return Response
                body = await result.read()
                simple_response = web.Response(
                    headers=headers,
                    status=result.status,
                    content_type=content_type,
                    body=body,
                    zlib_executor_size=32768,
                )
                if content_length_int > MIN_COMPRESSED_SIZE and should_compress(
                    content_type
                ):
                    simple_response.enable_compression()
                return simple_response

            # Stream response
            response = web.StreamResponse(status=result.status, headers=headers)
            response.content_type = content_type

            try:
                if should_compress(content_type):
                    response.enable_compression()
                await response.prepare(request)
                # In testing iter_chunked, iter_any, and iter_chunks:
                # iter_chunks was the best performing option since
                # it does not have to do as much re-assembly
                async for data, _ in result.content.iter_chunks():
                    await response.write(data)

            except (
                aiohttp.ClientError,
                aiohttp.ClientPayloadError,
                ConnectionResetError,
            ) as err:
                _LOGGER.debug("Stream error %s / %s: %s", token, path, err)

            return response


@lru_cache(maxsize=32)
def _forwarded_for_header(forward_for: str | None, peer_name: str) -> str:
    """Create X-Forwarded-For header."""
    connected_ip = ip_address(peer_name)
    return f"{forward_for}, {connected_ip!s}" if forward_for else f"{connected_ip!s}"


def _init_header(request: web.Request, token: str) -> CIMultiDict | dict[str, str]:
    """Create initial header."""
    headers = {
        name: value
        for name, value in request.headers.items()
        if name not in INIT_HEADERS_FILTER
    }
    # Ingress information
    headers[X_HASS_SOURCE] = "core.ingress"
    headers[X_INGRESS_PATH] = f"/api/hassio_ingress/{token}"

    # Set X-Forwarded-For
    forward_for = request.headers.get(hdrs.X_FORWARDED_FOR)
    assert request.transport
    if (peername := request.transport.get_extra_info("peername")) is None:
        _LOGGER.error("Can't set forward_for header, missing peername")
        raise HTTPBadRequest

    headers[hdrs.X_FORWARDED_FOR] = _forwarded_for_header(forward_for, peername[0])

    # Set X-Forwarded-Host
    if not (forward_host := request.headers.get(hdrs.X_FORWARDED_HOST)):
        forward_host = request.host
    headers[hdrs.X_FORWARDED_HOST] = forward_host

    # Set X-Forwarded-Proto
    forward_proto = request.headers.get(hdrs.X_FORWARDED_PROTO)
    if not forward_proto:
        forward_proto = request.scheme
    headers[hdrs.X_FORWARDED_PROTO] = forward_proto

    return headers


def _response_header(response: aiohttp.ClientResponse) -> dict[str, str]:
    """Create response header."""
    return {
        name: value
        for name, value in response.headers.items()
        if name not in RESPONSE_HEADERS_FILTER
    }


def _is_websocket(request: web.Request) -> bool:
    """Return True if request is a websocket."""
    headers = request.headers
    return bool(
        "upgrade" in headers.get(hdrs.CONNECTION, "").lower()
        and headers.get(hdrs.UPGRADE, "").lower() == "websocket"
    )


async def _websocket_forward(
    ws_from: web.WebSocketResponse | ClientWebSocketResponse,
    ws_to: web.WebSocketResponse | ClientWebSocketResponse,
) -> None:
    """Handle websocket message directly."""
    try:
        async for msg in ws_from:
            if msg.type is aiohttp.WSMsgType.TEXT:
                await ws_to.send_str(msg.data)
            elif msg.type is aiohttp.WSMsgType.BINARY:
                await ws_to.send_bytes(msg.data)
            elif msg.type is aiohttp.WSMsgType.PING:
                await ws_to.ping()
            elif msg.type is aiohttp.WSMsgType.PONG:
                await ws_to.pong()
            elif ws_to.closed:
                await ws_to.close(code=ws_to.close_code, message=msg.extra)  # type: ignore[arg-type]
    except RuntimeError:
        _LOGGER.debug("Ingress Websocket runtime error")
    except ConnectionResetError:
        _LOGGER.debug("Ingress Websocket Connection Reset")
