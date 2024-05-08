import asyncio
import logging
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
import websockets as websocket
from websockets import WebSocketClientProtocol
from websockets.exceptions import ConnectionClosedOK
import json

from .ledsc import LedSC
from .exceptions import CannotConnect

_LOGGER = logging.getLogger(__name__)


def setup_platform(
    hass: HomeAssistant, config, add_entities: AddEntitiesCallback, discovery_info=None
):
    __setup(hass, dict(config), add_entities)


async def async_setup_entry(
    hass: HomeAssistant, config: ConfigEntry, add_entities: AddEntitiesCallback
):
    await __setup(hass, dict(config.data), add_entities)


async def __setup(hass: HomeAssistant, config: dict, add_entities: AddEntitiesCallback):
    client = LedSClient(hass)
    await client.connect(host=config["host"], port=config["port"])
    add_entities(client.devices.values(), True)


class LedSClient:
    def __init__(self, hass: HomeAssistant) -> None:
        self.client: WebSocketClientProtocol | None = None
        self.connection_setup: tuple[str, int] | None = None
        self.devices: dict[str, LedSC] = {}
        self.ws_service_running = False
        self.hass = hass

    async def connect(self, host: str, port: int) -> bool:
        self.connection_setup = (host, port)
        if self.client is not None and not self.client.closed:
            raise CannotConnect(f"LedSClient: Already connected to {host}:{port}")
        _LOGGER.debug(f"LedSClient: Connecting to {host}:{port}")

        try:
            self.client = await websocket.connect(f"ws://{host}:{port}", open_timeout=2)
        except OSError:
            raise CannotConnect(
                f"LedSClient: Could not connect to websocket at {host}:{port}"
            )
        _LOGGER.info(f"LedSClient: Connected to {host}:{port}")
        initial_message = json.loads(await self.client.recv())

        if "dev" in initial_message:
            for name, data in initial_message["dev"].items():
                if name in self.devices:
                    device = self.devices[name]
                    await device.data(value=data)
                    device._client = self.client
                else:
                    self.devices[name] = LedSC(
                        name=name,
                        data=data,
                        client_id=f"{host}:{port}",
                        client=self.client,
                        hass=self.hass,
                    )

        _LOGGER.info(f"LedSClient: devices: {self.devices.keys()}")

        if not self.ws_service_running:
            self.hass.async_create_background_task(self.ws_service(), name="ledsc-ws")

        return True

    async def ws_service(self):
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
                    _LOGGER.warning(f"LedSClient: Connection closed. Reconnecting...")
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
        if self.client:
            await self.client.close()
