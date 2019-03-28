"""Hass.io Add-on ingress service."""
import asyncio
from typing import Union

import aiohttp
from aiohttp import web

from homeassistant.components.http import HomeAssistantView


class HassIOIngressView(HomeAssistantView):
    """Hass.io view to handle base part."""

    name = "api:hassio:ingress"
    url = "/api/hassio_ingress/{addon}/{path:.+}"
    requires_auth = False

    def __init__(self, host: str, websession: aiohttp.ClientSession):
        """Initialize a Hass.io ingress view."""
        self._host = host
        self._connector = websession.connector

    def _create_url(self, addon: str, path: str) -> str:
        """Create URL to service."""
        return "http://{}/addons/{}/web/{}".format(self._host, addon, path)

    async def _handle(
            self, request: web.Request, addon: str, path: str
    ) -> Union[web.Response, web.StreamResponse, web.WebSocketResponse]:
        """Route data to Hass.io ingress service."""
        header = request.headers

        # Create websession and aims cookies
        client = aiohttp.ClientSession(
            cookies=request.cookies, connector=self._connector
        )

        try:
            # Websocket
            if header["connection"] == "Upgrade" and\
                    header["upgrade"] == "websocket":
                return await self._handle_websocket(
                    client, request, addon, path
                )

            # Stream
            if header["transfer-encoding"] == "chunked":
                return await self._handle_stream(client, request, addon, path)

            # Request
            return await self._handle_request(client, request, addon, path)

        finally:
            client.detach()

    get = _handle
    post = _handle
    put = _handle
    delete = _handle

    async def _handle_websocket(
            self, client: aiohttp.ClientSession,
            request: web.Request, addon: str, path: str
    ) -> web.WebSocketResponse:
        """Ingress route for websocket."""
        ws_server = web.WebSocketResponse()
        await ws_server.prepare(request)

        # Start proxy
        url = self._create_url(addon, path)
        async with client.ws_connect(url) as ws_client:
            # Proxy requests
            await asyncio.wait(
                [
                    _websocket_forward(ws_server, ws_client),
                    _websocket_forward(ws_client, ws_server),
                ],
                return_when=asyncio.FIRST_COMPLETED
            )

        return ws_server

    async def _handle_stream(
            self, client: aiohttp.ClientSession,
            request: web.Request, addon: str, path: str
    ) -> web.StreamResponse:
        """Ingress route for stream."""

    async def _handle_request(
            self, client: aiohttp.ClientSession,
            request: web.Request, addon: str, path: str
    ) -> web.Response:
        """Ingress route for request."""

        url = self._create_url(addon, path)
        data = request.read()
        header = request.headers.copy()

        async with client.request(
                request.method, url, headers=header, data=data
        ) as result:
            headers = result.headers.copy()
            del headers['content-length']

            body = await result.read()

            # Return Response
            return web.Response(
                headers=headers,
                status=result.status,
                body=body
            )


async def _websocket_forward(ws_from, ws_to):
    """Handle websocket message directly."""
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
