"""The niko_home_control hub."""
from __future__ import annotations

import asyncio
import json
import logging

from nikohomecontrol import NikoHomeControlConnection
import voluptuous as vol

from homeassistant.const import CONF_HOST, CONF_NAME, CONF_PORT
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady

from .action import Action
from .const import DEFAULT_IP, DEFAULT_NAME, DEFAULT_PORT

_LOGGER = logging.getLogger(__name__)

DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_NAME, default=DEFAULT_NAME): str,
        vol.Required(CONF_HOST, default=DEFAULT_IP): str,
        vol.Required(CONF_PORT, default=DEFAULT_PORT): vol.Coerce(int),
    }
)


class Hub:
    """The niko home control hub."""

    manufacturer = "Niko"
    website = "https://niko.eu"

    def __init__(self, hass: HomeAssistant, name: str, host: str, port: str) -> None:
        """Init niko home control hub."""
        self._host = host
        self._port = port
        self._hass = hass
        self._name = name
        self._id = name
        self._listen_task = None
        self.entities = []
        try:
            self.connection = NikoHomeControlConnection(self._host, self._port)
            actions = []
            for action in self.list_actions():
                actions.append(Action(action, self))

            self._actions: list[Action] = list(actions)

        except asyncio.TimeoutError as ex:
            raise ConfigEntryNotReady(
                f"Timeout while connecting to {self._host}:{self._port}"
            ) from ex

        except BaseException as ex:
            raise ConfigEntryNotReady(
                f"Timeout while connecting to {self._host}:{self._port}"
            ) from ex

    @property
    def hub_id(self) -> str:
        """Id."""
        return self._id

    @property
    def data(self):
        """Data."""
        return self._data

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
        data = json.loads(self.connection.send(message))
        _LOGGER.debug(data)
        if "error" in data["data"] and data["data"]["error"] > 0:
            error = data["data"]["error"]
            if error == 100:
                raise "NOT_FOUND"
            if error == 200:
                raise "SYNTAX_ERROR"
            if error == 300:
                raise "ERROR"

        return list(data["data"])

    async def async_update(self):
        """Update data."""
        return await self._data.async_update()

    def get_action_state(self, action_id):
        """Get action state."""
        return self._data.get_state(action_id)

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

        _LOGGER.debug("listening")

        writer.write(s.encode())
        await writer.drain()
        async for line in reader:
            try:
                message = json.loads(line.decode())
                _LOGGER.debug(message)
                if message != "b\r":
                    if "event" in message and message["event"] == "listactions":
                        for _action in message["data"]:
                            entity = self.get_entity(_action["id"])
                            entity.update_state(_action["value1"])
            except:
                _LOGGER.debug("exception")
                _LOGGER.debug(line)

    def get_action(self, action_id):
        """Get action by id."""
        actions = [action for action in self._actions if action.action_id == action_id]
        return actions[0]

    def get_entity(self, action_id):
        """Get entity by id."""
        actions = [action for action in self.entities if action.id == action_id]
        return actions[0]

    def handle(self, pipeline, event):
        """Handle incoming action."""
        while True:
            if not pipeline.empty():
                message = pipeline.get()
                for _action in message.get("data"):
                    action = self.get_action(_action.get("id"))
                    action.update_state(_action.get("value1"))
