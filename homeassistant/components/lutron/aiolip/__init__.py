"""Implement the Lutron Integration Protocol."""

import asyncio
from collections.abc import Callable
import logging
from pathlib import Path
import urllib.request

__version__ = "1.1.7"

__all__ = [
    "Button",
    "Device",
    "Keypad",
    "KeypadComponent",
    "LIPGroupState",
    "LIPLedState",
    "Led",
    "LutronController",
    "LutronXmlDbParser",
    "OccupancyGroup",
    "Output",
    "Sysvar",
]

from .data import LIPAction, LIPGroupState, LIPLedState, LIPMessage, LIPMode
from .lutron_db import (
    Button,
    Device,
    Keypad,
    KeypadComponent,
    Led,
    LutronXmlDbParser,
    OccupancyGroup,
    Output,
    Sysvar,
)
from .protocol import LIP

_LOGGER = logging.getLogger(__name__)


class LutronController:
    """Main Lutron Controller class.

    This object owns the connection to the controller, the rooms that exist in the
    network, handles dispatch of incoming status updates, etc.
    """

    def __init__(
        self,
        hass,
        host,
        user,
        password,
        use_full_path,
        use_area_for_device_name,
        use_radiora_mode,
    ):
        """Initialize the Lutron controller."""
        self.hass = hass
        self.host = host
        self.lip = LIP()
        self.connected = False
        self.connect_lock = None
        self._subscribers: dict[
            tuple[int, int | None], list[Callable]
        ] = {}  # integration_id, component_number -> list of entities
        self.guid = None
        self.areas = []
        self.variables = []
        self.name = None
        self.use_full_path = use_full_path
        self.use_area_for_device_name = use_area_for_device_name
        self.use_radiora_mode = use_radiora_mode

    async def connect(self):
        """Connect to the Lutron controller."""
        if self.connect_lock is None:
            self.connect_lock = asyncio.Lock()
        async with self.connect_lock:
            if not self.connected:
                await self.lip.async_connect(self.host)
                self.connected = True
                self.hass.loop.create_task(self.lip.async_run())
                self.lip.set_callback(self._dispatch_message)

    def subscribe(self, integration_id, component_number, callback):
        """Subscribe the callable for a specific integration_id. Can be multiple entities for the same integration (e.g. keypad leds)."""
        key = (integration_id, component_number)
        self._subscribers.setdefault(key, []).append(callback)

    def _dispatch_message(self, msg: LIPMessage):
        """Call the function in the subscriber entity."""
        key = (msg.integration_id, msg.component_number)

        for cb in self._subscribers.get(key, []):
            match (msg.mode, msg.action_number):
                case (
                    (LIPMode.OUTPUT, LIPAction.OUTPUT_LEVEL)
                    | (LIPMode.GROUP, LIPAction.GROUP_STATE)
                    | (LIPMode.SYSVAR, LIPAction.SYSVAR_STATE)
                    | (LIPMode.DEVICE, LIPAction.DEVICE_LED_STATE)
                ):
                    cb(msg.value)
                case (
                    LIPMode.OUTPUT,
                    LIPAction.OUTPUT_UNDOCUMENTED_29 | LIPAction.OUTPUT_UNDOCUMENTED_30,
                ):
                    pass
                case (LIPMode.DEVICE, _):
                    cb(msg.action_number)
                case _:
                    # Optionally log or handle unknown message types
                    _LOGGER.debug("Unhandled LIP message: %s", msg)

    async def action(self, mode: LIPMode, *args):
        """Send an action command."""
        await self.connect()
        await self.lip.action(mode, *args)

    async def query(self, mode: LIPMode, *args):
        """Send a query command."""
        await self.connect()
        await self.lip.query(mode, *args)

    async def stop(self):
        """Stop the connection to the controller."""
        if self.connected:
            await self.lip.async_stop()
            self.connected = False

    async def output_set_level(
        self, output_id: int, new_level: float, fade_time: str | None = None
    ) -> None:
        """Set the level of an output."""
        await self.action(
            LIPMode.OUTPUT, output_id, LIPAction.OUTPUT_LEVEL, new_level, fade_time
        )

    async def output_get_level(self, output_id: int) -> None:
        """Query the level of an output."""
        await self.query(LIPMode.OUTPUT, output_id, LIPAction.OUTPUT_LEVEL)

    async def output_start_raising(self, output_id: int):
        """Start raising the motor."""
        await self.action(LIPMode.OUTPUT, output_id, LIPAction.OUTPUT_START_RAISING)

    async def output_start_lowering(self, output_id: int):
        """Start lowering the motor."""
        await self.action(LIPMode.OUTPUT, output_id, LIPAction.OUTPUT_START_LOWERING)

    async def output_stop(self, output_id: int):
        """Stop the motor."""
        await self.action(LIPMode.OUTPUT, output_id, LIPAction.OUTPUT_STOP)

    async def output_jog_raise(self, output_id: int):
        """Jog raise the motor."""
        await self.action(LIPMode.OUTPUT, output_id, LIPAction.OUTPUT_MOTOR_JOG_RAISE)

    async def output_jog_lower(self, output_id: int):
        """Jog lower the motor."""
        await self.action(LIPMode.OUTPUT, output_id, LIPAction.OUTPUT_MOTOR_JOG_LOWER)

    async def group_get_state(self, group_id: int) -> None:
        """Query the level of an output."""
        await self.query(LIPMode.GROUP, group_id, LIPAction.GROUP_STATE)

    async def device_press(self, keypad_id: int, component_number: int) -> None:
        """Triggers a simulated button press to the Keypad."""
        await self.action(
            LIPMode.DEVICE, keypad_id, component_number, LIPAction.DEVICE_PRESS
        )

    async def device_turn_on(self, keypad_id: int, component_number: int):
        """Turn on the LED."""
        await self.action(
            LIPMode.DEVICE,
            keypad_id,
            component_number,
            LIPAction.DEVICE_LED_STATE,
            LIPLedState.ON,
        )

    async def device_turn_off(self, keypad_id: int, component_number: int):
        """Turn off the LED."""
        await self.action(
            LIPMode.DEVICE,
            keypad_id,
            component_number,
            LIPAction.DEVICE_LED_STATE,
            LIPLedState.OFF,
        )

    async def device_get_state(self, keypad_id: int, component_number: int):
        """Get LED state."""
        await self.query(
            LIPMode.DEVICE, keypad_id, component_number, LIPAction.DEVICE_LED_STATE
        )

    async def sysvar_set_state(self, sysvar_id: int, value: int):
        """Set the variable."""
        await self.action(LIPMode.SYSVAR, sysvar_id, LIPAction.SYSVAR_STATE, value)

    async def sysvar_get_state(self, sysvar_id: int) -> None:
        """Get the Variable state."""
        await self.query(LIPMode.SYSVAR, sysvar_id, LIPAction.SYSVAR_STATE)

    def load_xml_db(
        self,
        cache_path=None,
        refresh_data=True,
        variable_ids=None,
    ):
        """Load the Lutron database from the server if refresh_data is True.

        If not, if a locally cached copy is available, use that instead, or
        create one and store it
        """

        xml_db = None
        loaded_from = None
        variable_ids = variable_ids or []

        if cache_path and not refresh_data:
            try:
                with Path.open(cache_path, "rb") as f:  # pylint: disable=unspecified-encoding
                    xml_db = f.read()
                    loaded_from = "cache"
            except OSError as e:
                _LOGGER.debug("Failed to read XML cache: %s", e)
        if not loaded_from:
            url = "http://" + self.host + "/DbXmlInfo.xml"
            with urllib.request.urlopen(url) as xmlfile:
                xml_db = xmlfile.read()
                loaded_from = "repeater"
                if cache_path and not refresh_data:
                    with Path.open(cache_path, "wb") as f:  # pylint: disable=unspecified-encoding
                        f.write(xml_db)
                        _LOGGER.info("Stored db as %s", cache_path)

        _LOGGER.info("Loaded xml db from %s", loaded_from)

        parser = LutronXmlDbParser(
            xml_db_str=xml_db,
            variable_ids=variable_ids,
        )
        assert parser.parse()  # throw our own exception
        self.areas = parser.areas
        self.name = parser.project_name
        self.variables = parser.variables
        self.guid = parser.lutron_guid

        _LOGGER.info("Found Lutron project: %s, %d areas", self.name, len(self.areas))

        if cache_path and loaded_from == "repeater":
            with Path.open(cache_path, "wb") as f:  # pylint: disable=unspecified-encoding
                f.write(xml_db)

        return True
