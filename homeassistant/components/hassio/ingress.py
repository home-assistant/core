"""Hass.io Add-on ingress service."""
import asyncio
from ipaddress import ip_address
import os
from typing import Dict, Union

import aiohttp
from aiohttp import web
from aiohttp.hdrs import (
    CONNECTION, CONTENT_LENGTH, UPGRADE, X_FORWARDED_FOR, X_FORWARDED_HOST,
    X_FORWARDED_PROTO)
from multidict import CIMultiDict

from homeassistant.components.http import HomeAssistantView

from .const import X_HASSIO


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
            if header[CONNECTION] == "Upgrade" and\
                    header[UPGRADE] == "websocket":
                return await self._handle_websocket(
                    client, request, addon, path
                )

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

        url = self._create_url(addon, path)
        source_header = _init_header(request, False)

        # Start proxy
        async with client.ws_connect(url, headers=source_header) as ws_client:
            # Proxy requests
            await asyncio.wait(
                [
                    _websocket_forward(ws_server, ws_client),
                    _websocket_forward(ws_client, ws_server),
                ],
                return_when=asyncio.FIRST_COMPLETED
            )

        return ws_server

    async def _handle_request(
            self, client: aiohttp.ClientSession,
            request: web.Request, addon: str, path: str
    ) -> Union[web.Response, web.StreamResponse]:
        """Ingress route for request."""

        url = self._create_url(addon, path)
        data = request.read()
        source_header = _init_header(request, True)

        async with client.request(
                request.method, url, headers=source_header, data=data
        ) as result:
            headers = result.headers.copy()

            # Simple request
            if CONTENT_LENGTH in headers:
                del headers[CONTENT_LENGTH]

                # Return Response
                body = await result.read()
                return web.Response(
                    headers=headers,
                    status=result.status,
                    body=body
                )

            # Stream response
            response = web.StreamResponse(
                status=result.status, headers=headers)
            response.content_type = result.content_type

            try:
                await response.prepare(request)
                async for data in result.content:
                    await response.write(data)

            except (aiohttp.ClientError, aiohttp.ClientPayloadError):
                pass

            return response


def _init_header(
        request: web.Request, use_source: bool
) -> Union[CIMultiDict, Dict[str, str]]:
    """Create initial header."""
    if use_source:
        headers = request.headers.copy()
    else:
        headers = {}

    # Inject token / cleanup later on Supervisor
    headers[X_HASSIO] = os.environ.get('HASSIO_TOKEN', "")

    # Set X-Forwarded-For
    forward_for = request.headers.get(X_FORWARDED_FOR)
    connected_ip = ip_address(request.transport.get_extra_info('peername')[0])
    if forward_for:
        forward_for = "{}, {!s}".format(forward_for, connected_ip)
    else:
        forward_for = "{!s}".format(connected_ip)
    headers[X_FORWARDED_FOR] = forward_for

    # Set X-Forwarded-Host
    forward_host = request.headers.get(X_FORWARDED_HOST)
    if not forward_host:
        forward_host = request.host
    headers[X_FORWARDED_HOST] = forward_host

    # Set X-Forwarded-Host
    forward_proto = request.headers.get(X_FORWARDED_PROTO)
    if not forward_proto:
        forwad_proto = request.url.schema
    headers[X_FORWARDED_PROTO] = forward_proto

    return headers


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
