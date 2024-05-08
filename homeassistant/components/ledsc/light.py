"""LedSC light."""

import asyncio
import json
import logging

import websockets as websocket
from websockets import WebSocketClientProtocol
from websockets.exceptions import ConnectionClosedOK

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .exceptions import CannotConnect
from .ledsc import LedSC

_LOGGER = logging.getLogger(__name__)


def setup_platform(
    hass: HomeAssistant, config, add_entities: AddEntitiesCallback, discovery_info=None
):
    """Redirects to '__setup'."""
    hass.async_create_task(__setup(hass, dict(config), add_entities))


async def async_setup_entry(
    hass: HomeAssistant, config: ConfigEntry, add_entities: AddEntitiesCallback
):
    """Redirects to '__setup'."""
    await __setup(hass, dict(config.data), add_entities)


async def __setup(hass: HomeAssistant, config: dict, add_entities: AddEntitiesCallback):
    """
    Connect to WebSC.

    load the configured devices and add them to hass.
    """
    client = LedSClient(hass)
    await client.connect(host=config["host"], port=config["port"])
    add_entities(client.devices.values(), True)


class LedSClient:
    """Client for LedSC devices. Mediates websocket communication with WebSC."""

    def __init__(self, hass: HomeAssistant) -> None:
        """Set variables to default values."""
        self.client: WebSocketClientProtocol | None = None
        self.connection_setup: tuple[str, int] | None = None
        self.devices: dict[str, LedSC] = {}
        self.ws_service_running = False
        self.hass = hass

    async def connect(self, host: str, port: int) -> bool:
        """
        Connect to WebSC.

        Read configuration from initial message and create LedSC devices.
        Create background task for websocket listening.
        """
        self.connection_setup = (host, port)
        if self.client is not None and not self.client.closed:
            raise CannotConnect(f"LedSClient: Already connected to {host}:{port}")
        _LOGGER.debug(f"LedSClient: Connecting to %s:%s", host, port)

        try:
            self.client = await websocket.connect(f"ws://{host}:{port}", open_timeout=2)
        except OSError as E:
            raise CannotConnect(
                f"LedSClient: Could not connect to websocket at {host}:{port}"
            ) from E
        _LOGGER.info(f"LedSClient: Connected to %s:%s", host, port)
        initial_message = json.loads(await self.client.recv())

        if "dev" in initial_message:
            for name, data in initial_message["dev"].items():
                if name in self.devices:
                    device = self.devices[name]
                    await device.data(value=data)
                    device.client = self.client
                else:
                    self.devices[name] = LedSC(
                        name=name,
                        data=data,
                        client_id=f"{host}:{port}",
                        client=self.client,
                        hass=self.hass,
                    )

        _LOGGER.info(f"LedSClient: devices: %s", self.devices.keys())

        if not self.ws_service_running:
            self.hass.async_create_background_task(self.ws_service(), name="ledsc-ws")

        return True

    async def ws_service(self):
        """Listen on the WebSC and resending data to the LedSC devices."""
        try:
            self.ws_service_running = True
            while True:
                try:
                    _data = json.loads(await self.client.recv())
                    if "dev" in _data:
                        for name, data in _data["dev"].items():
                            if name in self.devices:
                                await self.devices[name].data(data)
                except ConnectionClosedOK:
                    _LOGGER.warning("LedSClient: Connection closed. Reconnecting...")
                    for device in self.devices.values():
                        await device.data({"is_lost": 1})
                    while self.client.closed:
                        try:
                            await self.connect(*self.connection_setup)
                            await asyncio.sleep(1)
                        except CannotConnect:
                            await asyncio.sleep(5)
        finally:
            self.ws_service_running = False
            await self.disconnect()

    async def disconnect(self) -> None:
        """Disconnect from WebSC."""
        if self.client:
            await self.client.close()
