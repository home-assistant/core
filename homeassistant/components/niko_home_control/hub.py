"""The niko_home_control hub."""
from __future__ import annotations

import asyncio
import json
import logging

import voluptuous as vol

from homeassistant.const import CONF_HOST, CONF_NAME, CONF_PORT
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers import device_registry as dr

from .action import Action
from .const import DEFAULT_IP, DEFAULT_NAME, DEFAULT_PORT, DOMAIN
from .controller import NikoHomeControlController
from .cover import NikoHomeControlCover
from .fan import NikoHomeControlFan
from .light import NikoHomeControlDimmableLight, NikoHomeControlLight

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

    def __init__(
        self, hass: HomeAssistant, name: str, host: str, port: int, entry_id: str
    ) -> None:
        """Init niko home control hub."""
        self._host = host
        self._port = port
        self._hass = hass
        self._name = name
        self._controller = NikoHomeControlController(host, port)
        self._via_device = (DOMAIN, entry_id)
        self._device_info = {
            "identifiers": {(DOMAIN, entry_id)},
            "manufacturer": "Niko",
            "model": "Connected controller (550-00004)",
            "name": name,
            "sw_version": self._controller.system_info()["swversion"],
            "hw_version": "1.0",
            "suggested_area": "garage",
        }

        device_registry = dr.async_get(hass)

        device_registry.async_get_or_create(
            config_entry_id=entry_id,
            identifiers={(DOMAIN, entry_id)},
            manufacturer="Niko",
            suggested_area="Garage",
            name=name,
            model="Connected controller (550-00004)",
            sw_version=self._controller.system_info()["swversion"],
            hw_version="1.0",
        )
        self._id = entry_id
        self._listen_task = None
        self._is_connected = False

        self.entities: list[
            NikoHomeControlLight
            | NikoHomeControlDimmableLight
            | NikoHomeControlCover
            | NikoHomeControlFan
        ] = []
        self._actions: list[Action] = []
        self._locations = {}

        try:
            _locations = self._controller.list_locations()
            for location in _locations:
                self._locations[location["id"]] = location["name"]

            for action in self._controller.list_actions():
                _LOGGER.debug(action)
                self._actions.append(Action(action, self))

            self._is_connected = True

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
    def is_connected(self) -> bool:
        """Is connected."""
        return self._is_connected

    @property
    def ip_address(self) -> str:
        """IP."""
        return self._host

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
        return self._controller.execute_actions(action_id, action_value)

    def start_events(self):
        """Start events."""
        self._listen_task = asyncio.create_task(self.listen())

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
