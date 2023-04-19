"""View to accept incoming websocket connection."""
from __future__ import annotations

import asyncio
from collections.abc import Callable
from contextlib import suppress
import datetime as dt
import logging
from typing import TYPE_CHECKING, Any, Final

from aiohttp import WSMsgType, web
import async_timeout

from homeassistant.components.http import HomeAssistantView
from homeassistant.const import EVENT_HOMEASSISTANT_STOP
from homeassistant.core import Event, HomeAssistant, callback
from homeassistant.helpers.dispatcher import async_dispatcher_send
from homeassistant.helpers.event import async_call_later
from homeassistant.util.json import json_loads


_WS_LOGGER: Final = logging.getLogger(f"{__name__}.connection")


class WebsocketAPIView(HomeAssistantView):
    """View to serve a websockets endpoint."""

    name: str = "websocketapi_custom"
    url: str =  "/api/websocket_custom"
    requires_auth: bool = False

    async def get(self, request: web.Request) -> web.WebSocketResponse:
        """Handle an incoming websocket connection."""
        return await WebSocketHandler(request.app["hass"], request).async_handle()


class WebSocketAdapter(logging.LoggerAdapter):
    """Add connection id to websocket messages."""

    def process(self, msg: str, kwargs: Any) -> tuple[str, Any]:
        """Add connid to websocket log messages."""
        if not self.extra or "connid" not in self.extra:
            return msg, kwargs
        return f'[{self.extra["connid"]}] {msg}', kwargs


class WebSocketHandler:
    """Handle an active websocket client connection."""

    def __init__(self, hass: HomeAssistant, request: web.Request) -> None:
        """Initialize an active connection."""
        self.hass = hass
        self.request = request
        self.wsock = web.WebSocketResponse(heartbeat=55)
       
        self._logger = WebSocketAdapter(_WS_LOGGER, {"connid": id(self)})

    async def async_handle(self) -> web.WebSocketResponse:
        """Handle a websocket response."""
        request = self.request
        wsock = self.wsock

        await wsock.prepare(request)
        
        try:
            await wsock.send_str("1")

            while True:
                msg = await wsock.receive()
                msg_data = msg.json(loads=json_loads) + 1
                print(msg_data)
                await wsock.send_str(str(msg_data))
                await asyncio.sleep(1)

        except asyncio.CancelledError:
            self._logger.info("Connection closed by client")

        except Exception:  # pylint: disable=broad-except
            self._logger.exception("Unexpected error inside websocket API")
        
        return wsock
