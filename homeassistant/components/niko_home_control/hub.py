"""The niko_home_control hub."""
from __future__ import annotations

import asyncio
import concurrent.futures
import json
import queue
import threading

from nikohomecontrol import NikoHomeControlConnection
import voluptuous as vol

from homeassistant.const import CONF_HOST, CONF_NAME, CONF_PORT
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady

from .action import Action
from .const import DEFAULT_IP, DEFAULT_NAME, DEFAULT_PORT

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
        pipeline = queue.Queue(maxsize=10)
        event = threading.Event()
        with concurrent.futures.ThreadPoolExecutor(max_workers=2) as executor:
            executor.submit(self.listen, pipeline, event)
            executor.submit(self.handle, pipeline, event)
            event.set()

    def list_actions(self):
        """List all actions."""
        return self._execute('{"cmd":"listactions"}')

    def listen(self, pipeline, event):
        """Listen for events."""
        self._execute('{"cmd":"startevents"}')
        while True:
            data = self.connection.receive()
            if not data:
                break
            if not data.isspace():
                pipeline.put(json.loads(data))

    def get_action(self, action_id):
        """Get action by id."""
        actions = [action for action in self._actions if action.action_id == action_id]
        return actions[0]

    def handle(self, pipeline, event):
        """Handle incoming action."""
        while True:
            if not pipeline.empty():
                message = pipeline.get()
                for _action in message.get("data"):
                    action = self.get_action(_action.get("id"))
                    action.update_state(_action.get("value1"))
