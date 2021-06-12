"""AIS zwave2mqtt ingress service."""
import asyncio
from ipaddress import ip_address
import logging
from typing import Dict, Union

import aiohttp
from aiohttp import hdrs, web
from aiohttp.web_exceptions import HTTPBadGateway, HTTPUnauthorized
from multidict import CIMultiDict

from homeassistant.components.http import HomeAssistantView
from homeassistant.core import callback
from homeassistant.helpers.typing import HomeAssistantType

from .const import X_HASSIO, X_INGRESS_PATH

_LOGGER = logging.getLogger(__name__)
DOMAIN = "ais_web_zwave2mqtt"


@callback
def async_setup_ingress_view(hass: HomeAssistantType, host: str, port: int):
    """Auth setup."""
    websession = hass.helpers.aiohttp_client.async_get_clientsession()

    hassio_ingress = HassIOIngress(hass, host, port, websession)
    hass.http.register_view(hassio_ingress)


class HassIOIngress(HomeAssistantView):
    """Hass.io view to handle base part."""

    name = "api:zwave2mqtt"
    url = "/api/zwave2mqtt/{token}/{path:.*}"
    requires_auth = False

    def __init__(
        self,
        hass: HomeAssistantType,
        host: str,
        port: int,
        websession: aiohttp.ClientSession,
    ):
        """Initialize a Hass.io ingress view."""
        self._host = host
        self._port = port
        self._hass = hass
        self._websession = websession
        self._valid_token = ""

    def _create_url(self, token: str, path: str) -> str:
        """Create URL to service."""
        return f"http://{self._host}:{self._port}/{path}"

    async def _handle(
        self, request: web.Request, token: str, path: str
    ) -> Union[web.Response, web.StreamResponse, web.WebSocketResponse]:
        """Route data to Hass.io ingress service."""
        # validate token
        if token != self._valid_token:
            try:
                auth = self._hass.auth
                refresh_token = await auth.async_validate_access_token(token)
                if refresh_token is None:
                    raise HTTPUnauthorized() from None
                # remember the token as valid
                self._valid_token = token
            except Exception:
                raise HTTPUnauthorized() from None

        try:
            # Websockettoken
            if _is_websocket(request):
                return await self._handle_websocket(request, token, path)

            # Request
            return await self._handle_request(request, token, path)

        except aiohttp.ClientError as err:
            _LOGGER.debug("Ingress error with %s / %s: %s", token, path, err)

        raise HTTPBadGateway() from None

    get = _handle
    post = _handle
    put = _handle
    delete = _handle
    patch = _handle
    options = _handle

    async def _handle_websocket(
        self, request: web.Request, token: str, path: str
    ) -> web.WebSocketResponse:
        """Ingress route for websocket."""
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
            url = f"{url}?{request.query_string}"

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
                    _websocket_forward(ws_server, ws_client),
                    _websocket_forward(ws_client, ws_server),
                ],
                return_when=asyncio.FIRST_COMPLETED,
            )

        return ws_server

    async def _handle_request(
        self, request: web.Request, token: str, path: str
    ) -> Union[web.Response, web.StreamResponse]:
        """Ingress route for request."""
        url = self._create_url(token, path)
        data = await request.read()
        source_header = _init_header(request, token)

        async with self._websession.request(
            request.method,
            url,
            headers=source_header,
            params=request.query,
            allow_redirects=False,
            data=data,
        ) as result:
            headers = _response_header(result)

            # Simple request
            if (
                hdrs.CONTENT_LENGTH in result.headers
                and int(result.headers.get(hdrs.CONTENT_LENGTH, 0)) < 4194000
            ):
                # Return Response
                body = await result.read()
                return web.Response(
                    headers=headers,
                    status=result.status,
                    content_type=result.content_type,
                    body=body,
                )

            # Stream response
            response = web.StreamResponse(status=result.status, headers=headers)
            response.content_type = result.content_type

            try:
                await response.prepare(request)
                async for data in result.content.iter_chunked(4096):
                    await response.write(data)

            except (aiohttp.ClientError, aiohttp.ClientPayloadError) as err:
                _LOGGER.debug("Stream error %s / %s: %s", token, path, err)

            return response


def _init_header(
    request: web.Request, token: str
) -> Union[CIMultiDict, Dict[str, str]]:
    """Create initial header."""
    headers = {}

    # filter flags
    for name, value in request.headers.items():
        if name in (
            hdrs.CONTENT_LENGTH,
            hdrs.CONTENT_ENCODING,
            hdrs.SEC_WEBSOCKET_EXTENSIONS,
            hdrs.SEC_WEBSOCKET_PROTOCOL,
            hdrs.SEC_WEBSOCKET_VERSION,
            hdrs.SEC_WEBSOCKET_KEY,
        ):
            continue
        headers[name] = value

    # Inject token
    # headers[X_HASSIO] = os.environ.get("HASSIO_TOKEN", "")
    headers[X_HASSIO] = token

    # Ingress information
    # headers[X_INGRESS_PATH] = f"/api/zwave2mqtt/{token}"
    headers["X-External-Path"] = f"/api/zwave2mqtt/{token}"

    # Set X-Forwarded-For
    forward_for = request.headers.get(hdrs.X_FORWARDED_FOR)
    connected_ip = ip_address(request.transport.get_extra_info("peername")[0])
    if forward_for:
        forward_for = f"{forward_for}, {connected_ip!s}"
    else:
        forward_for = f"{connected_ip!s}"
    headers[hdrs.X_FORWARDED_FOR] = forward_for

    # Set X-Forwarded-Host
    forward_host = request.headers.get(hdrs.X_FORWARDED_HOST)
    if not forward_host:
        forward_host = request.host
    headers[hdrs.X_FORWARDED_HOST] = forward_host

    # Set X-Forwarded-Proto
    forward_proto = request.headers.get(hdrs.X_FORWARDED_PROTO)
    if not forward_proto:
        forward_proto = request.url.scheme
    headers[hdrs.X_FORWARDED_PROTO] = forward_proto

    return headers


def _response_header(response: aiohttp.ClientResponse) -> Dict[str, str]:
    """Create response header."""
    headers = {}

    for name, value in response.headers.items():
        if name in (
            hdrs.TRANSFER_ENCODING,
            hdrs.CONTENT_LENGTH,
            hdrs.CONTENT_TYPE,
            hdrs.CONTENT_ENCODING,
        ):
            continue
        headers[name] = value

    return headers


def _is_websocket(request: web.Request) -> bool:
    """Return True if request is a websocket."""
    headers = request.headers

    if (
        "upgrade" in headers.get(hdrs.CONNECTION, "").lower()
        and headers.get(hdrs.UPGRADE, "").lower() == "websocket"
    ):
        return True
    return False


async def _websocket_forward(ws_from, ws_to):
    """Handle websocket message directly."""
    try:
        async for msg in ws_from:
            if msg.type == aiohttp.WSMsgType.TEXT:
                await ws_to.send_str(msg.data)
            elif msg.type == aiohttp.WSMsgType.BINARY:
                await ws_to.send_bytes(msg.data)
            elif msg.type == aiohttp.WSMsgType.PING:
                await ws_to.ping()
            elif msg.type == aiohttp.WSMsgType.PONG:
                await ws_to.pong()
            elif ws_to.closed:
                await ws_to.close(code=ws_to.close_code, message=msg.extra)
    except RuntimeError:
        _LOGGER.debug("Ingress Websocket runtime error")


async def async_setup(hass, config):
    """Set up the  component."""
    config = config.get(DOMAIN, {})
    host = config.get("host")
    port = config.get("port")
    # Init ingress feature
    async_setup_ingress_view(hass, host, port)

    return True
