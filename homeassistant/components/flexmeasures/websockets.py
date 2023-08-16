"""View to accept incoming websocket connection."""
from __future__ import annotations

import asyncio
import json
import logging
from typing import Any, Final

import aiohttp
from aiohttp import web
from flexmeasures_client.s2.cem import CEM
import pyfiglet
from python_s2_protocol.common.schemas import ControlType
from rich import print
from rich.align import Align
from rich.json import JSON
from rich.panel import Panel

from homeassistant.components.http import HomeAssistantView
from homeassistant.core import HomeAssistant

_WS_LOGGER: Final = logging.getLogger(f"{__name__}.connection")


class WebsocketAPIView(HomeAssistantView):
    """View to serve a websockets endpoint."""

    name: str = "websocketapi_custom"
    url: str = "/api/websocket_custom"
    requires_auth: bool = False
    cem: CEM

    def __init__(self, cem: CEM) -> None:
        """Expose WebSocket server via an API view.

        :param cem: Customer Energy Manager
        """
        super().__init__()
        self.cem = cem

        title = pyfiglet.figlet_format("CEM", font="standard")
        print(
            Align(Panel(f"[red]{title}[/red]", style="black on white"), align="center")
        )

    async def get(self, request: web.Request) -> web.WebSocketResponse:
        """Handle an incoming websocket connection."""
        self.cem._control_type = None
        return await WebSocketHandler(
            request.app["hass"], request, self.cem
        ).async_handle()


class WebSocketAdapter(logging.LoggerAdapter):
    """Add connection id to websocket messages."""

    def process(self, msg: str, kwargs: Any) -> tuple[str, Any]:
        """Add connid to websocket log messages."""
        if not self.extra or "connid" not in self.extra:
            return msg, kwargs
        return f'[{self.extra["connid"]}] {msg}', kwargs


class WebSocketHandler:
    """Handle an active websocket client connection."""

    def __init__(self, hass: HomeAssistant, request: web.Request, cem: CEM) -> None:
        """Initialize an active connection."""
        self.hass = hass
        self.request = request
        self.wsock = web.WebSocketResponse(heartbeat=55)
        self.cem = cem

        self._logger = WebSocketAdapter(_WS_LOGGER, {"connid": id(self)})

    async def rm_details_watchdog(self) -> None:
        """Define a service in Home Assistant, or could be a HTTP endpoint to trigger schedules.

        Args:
            ws: websockets object
            cem (CEM): Customer Energy Manager
        """
        cem = self.cem

        # wait to get resource manager details
        while cem._control_type is None:
            await asyncio.sleep(1)

        await cem.activate_control_type(
            control_type=ControlType.FILL_RATE_BASED_CONTROL
        )

        # check/wait that the control type is set properly
        async with asyncio.timeout(10):
            while cem._control_type != ControlType.FILL_RATE_BASED_CONTROL:
                print("waiting for the activation of the control type...")
                await asyncio.sleep(1)

        print("CONTROL TYPE: ", cem._control_type)

        # after this, schedule will be triggered on reception of a new system description

    async def _websocket_producer(self):
        cem = self.cem

        print("[bold]New connection[/bold]")
        # print("start websocket message producer")

        while not cem.is_closed():
            message = await cem.get_message()

            print(Panel(JSON(json.dumps(message)), title="Sending", expand=False))

            await self.wsock.send_json(message)
        print("cem closed")

    async def _websocket_consumer(self):
        cem = self.cem

        async for msg in self.wsock:
            message = json.loads(msg.json())
            print(
                Panel(
                    JSON(json.dumps(message)),
                    title=f"Receiving - {message.get('message_type')}",
                    expand=False,
                )
            )

            if msg.type == aiohttp.WSMsgType.TEXT:
                if msg.data == "close":
                    # TODO: save cem state?
                    print("close...")
                    cem.close()
                    await self.wsock.close()
                else:
                    await cem.handle_message(message)

            elif msg.type == aiohttp.WSMsgType.ERROR:
                print("close...")
                cem.close()
                print("ws connection closed with exception %s" % self.wsock.exception())
                # TODO: save cem state?

        print("websocket connection closed")

    async def async_handle(self) -> web.WebSocketResponse:
        """Handle a websocket response."""
        request = self.request
        wsock = self.wsock

        await wsock.prepare(request)

        # create "parallel" tasks for the message producer and consumer
        await asyncio.gather(
            self._websocket_consumer(),
            self._websocket_producer(),
            # self.rm_details_watchdog(),
        )

        return wsock
