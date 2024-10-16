"""The niko_home_control hub."""
from __future__ import annotations

import asyncio
import json
import logging

from nikohomecontrol import NikoHomeControlConnection
import voluptuous as vol

from homeassistant.const import CONF_HOST, CONF_NAME, CONF_PORT
from homeassistant.components.device_tracker import DeviceScanner
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady

from .action import Action
from .const import DEFAULT_IP, DEFAULT_NAME, DEFAULT_PORT
from .cover import NikoHomeControlCover
from .light import NikoHomeControlDimmableLight, NikoHomeControlLight

_LOGGER = logging.getLogger(__name__)

DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_NAME, default=DEFAULT_NAME): str,
        vol.Required(CONF_HOST, default=DEFAULT_IP): str,
        vol.Required(CONF_PORT, default=DEFAULT_PORT): vol.Coerce(int),
    }
)


class Hub(DeviceScanner):
    """The niko home control hub."""

    manufacturer = "Niko"
    website = "https://niko.eu"
    model = "P.O.M"  # Peace Of Mind
    version = "1.0" # The Niko Home Control controller version

    def __init__(self, hass: HomeAssistant, name: str, host: str, port: int) -> None:
        """Init niko home control hub."""
        self._host = host
        self._port = port
        self._hass = hass
        self._name = name
        self._id = name
        self._listen_task = None

        self.entities: list[
            NikoHomeControlLight | NikoHomeControlDimmableLight | NikoHomeControlCover
        ] = []
        self._actions: list[Action] = []
        try:
            self.connection = NikoHomeControlConnection(self._host, self._port)
            self._is_connected = True
            for action in self.list_actions():
                self._actions.append(Action(action, self))

        except asyncio.TimeoutError as ex:
            self._is_connected = False
            raise ConfigEntryNotReady(
                f"Timeout while connecting to {self._host}:{self._port}"
            ) from ex

        except BaseException as ex:
            self._is_connected = False
            raise ConfigEntryNotReady(
                f"Timeout while connecting to {self._host}:{self._port}"
            ) from ex

    @property
    def ip_address(self) -> str:
        return self._host

    @property
    def is_connected(self) -> bool:
        return self._is_connected

    @property
    def hub_id(self) -> str:
        """Id."""
        return self._id

    @property
    def actions(self):
        """Actions."""
        return self._actions

    def execute_actions(self, action_id, action_value):
        """Execute Actions."""
        return self._execute(
            '{"cmd":"executeactions", "id": "'
            + str(action_id)
            + '", "value1": "'
            + str(action_value)
            + '"}'
        )

    def _execute(self, message):
        """Execute command."""
        message = json.loads(self.connection.send(message))
        if "error" in message["data"] and message["data"]["error"] > 0:
            error = message["data"]["error"]
            if error == 100:
                raise FileNotFoundError("NOT_FOUND")
            if error == 200:
                raise SyntaxError("SYNTAX_ERROR")
            if error == 300:
                raise ValueError("ERROR")

        return list(message["data"])

    def start_events(self):
        """Start events."""
        self._listen_task = asyncio.create_task(self.listen())

    def list_actions(self):
        """List all actions."""
        return self._execute('{"cmd":"listactions"}')

    async def listen(self):
        """Listen for events."""
        s = '{"cmd":"startevents"}'
        reader, writer = await asyncio.open_connection(self._host, self._port)

        writer.write(s.encode())
        await writer.drain()

        async for line in reader:
            try:
                message = json.loads(line.decode())
                _LOGGER.debug("Received: %s", message)
                if message != "b\r":
                    if "event" in message and message["event"] == "listactions":
                        for _action in message["data"]:
                            entity = self.get_entity(_action["id"])
                            entity.update_state(_action["value1"])
            except any:
                _LOGGER.debug("exception")
                _LOGGER.debug(line)

    def get_entity(self, action_id):
        """Get entity by id."""
        actions = [action for action in self.entities if action.id == action_id]
        return actions[0]
