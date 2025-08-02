"""Implement the Lutron Integration Protocol."""

import asyncio
from collections.abc import Callable
import logging
from pathlib import Path
from typing import Any
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

from .data import (
    LIPAction,
    LIPCommand,
    LIPGroupState,
    LIPLedState,
    LIPMessage,
    LIPMode,
    LIPOperation,
)
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
from .protocol import LIP, LIPConnectionState

_LOGGER = logging.getLogger(__name__)


class LutronController:
    """Main Lutron Controller class.

    This object owns the connection to the controller, the rooms that exist in the
    network, handles dispatch of incoming status updates, etc.
    """

    def __init__(
        self,
        hass: Any,  # HomeAssistant type
        host: str,
        user: str,
        password: str,
        use_full_path: bool,
        use_area_for_device_name: bool,
        use_radiora_mode: bool,
    ) -> None:
        """Initialize the Lutron controller.

        Args:
            hass: Home Assistant instance
            host: Hostname or IP address of the Lutron controller
            user: Username for authentication
            password: Password for authentication
            use_full_path: Whether to use full path for area names
            use_area_for_device_name: Whether to include area in device names
            use_radiora_mode: Whether to use RadioRA compatibility mode

        """
        self.hass = hass
        self.host = host
        self.user = user
        self.password = password
        self.lip = LIP()
        self.connect_lock: asyncio.Lock | None = None
        self._subscribers: dict[
            tuple[int, int | None], list[Callable[[Any], None]]
        ] = {}  # integration_id, component_number -> list of entities
        self.guid: str = "no guid"
        self.areas: list[Any] = []  # List[Area] type
        self.variables: list[Sysvar] = []
        self.name: str | None = None
        self.use_full_path = use_full_path
        self.use_area_for_device_name = use_area_for_device_name
        self.use_radiora_mode = use_radiora_mode

    @property
    def connected(self) -> bool:
        """Return the connection state of the LutronController."""
        if self.lip is None:
            return False
        return self.lip.connection_state == LIPConnectionState.CONNECTED

    async def connect(self):
        """Connect to the Lutron controller."""
        if self.connect_lock is None:
            self.connect_lock = asyncio.Lock()
        async with self.connect_lock:
            if not self.connected:
                await self.lip.async_connect(self.host)
                if self.connected:
                    self.hass.loop.create_task(self.lip.async_run())
                    self.lip.set_callback(self._dispatch_message)

    def subscribe(self, integration_id, component_number, callback):
        """Subscribe the callable for a specific integration_id. Can be multiple entities for the same integration (e.g. keypad leds)."""
        key = (integration_id, component_number)
        self._subscribers.setdefault(key, []).append(callback)

    def unsubscribe(
        self,
        integration_id: int,
        component_number: int | None,
        callback: Callable[[Any], None],
    ) -> None:
        """Unsubscribe from updates for a specific integration_id and component_number."""
        key = (integration_id, component_number)
        if key in self._subscribers:
            self._subscribers[key].remove(callback)
            if not self._subscribers[key]:
                del self._subscribers[key]

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

    async def execute_command(self, command: LIPCommand) -> None:
        """Execute a LIPCommand."""
        await self._ensure_connected()

        # Build args list
        args: list[Any] = [command.integration_id]
        if command.component_number is not None:
            args.append(command.component_number)
        if command.action is not None:
            args.append(command.action)
        if command.value is not None:
            args.append(command.value)
        if command.fade_time is not None:
            args.append(command.fade_time)

        # Use the appropriate method based on operation
        if command.operation == LIPOperation.EXECUTE:
            await self.lip.action(command.mode, *args)
        elif command.operation == LIPOperation.QUERY:
            await self.lip.query(command.mode, *args)
        else:
            raise ValueError(f"Unsupported operation: {command.operation}")

    async def action(self, mode: LIPMode, *args):
        """Send an action command (legacy method)."""
        await self._ensure_connected()
        await self.lip.action(mode, *args)

    async def query(self, mode: LIPMode, *args):
        """Send a query command (legacy method)."""
        await self._ensure_connected()
        await self.lip.query(mode, *args)

    async def stop(self):
        """Stop the connection to the controller."""
        if self.connected:
            await self.lip.async_stop()

    async def _ensure_connected(self) -> None:
        """Ensure the controller is connected before sending commands."""
        if not self.connected:
            await self.connect()

    def load_xml_db(
        self,
        cache_path: str | None = None,
        refresh_data: bool = True,
        variable_ids: list[int] | None = None,
    ) -> bool:
        """Load the Lutron database from the server if refresh_data is True.

        If not, if a locally cached copy is available, use that instead, or
        create one and store it

        Args:
            cache_path: Path to cache the XML database
            refresh_data: Whether to refresh data from server
            variable_ids: List of variable IDs to include

        Returns:
            True if successful

        Raises:
            Exception: If database loading fails

        """
        xml_db = None
        loaded_from = None
        variable_ids = variable_ids or []

        if cache_path and not refresh_data:
            try:
                with Path(cache_path).open("rb") as f:  # pylint: disable=unspecified-encoding
                    xml_db = f.read()
                    loaded_from = "cache"
                    _LOGGER.debug("Loaded XML database from cache: %s", cache_path)
            except OSError as e:
                _LOGGER.debug("Failed to read XML cache: %s", e)

        if not loaded_from:
            url = "http://" + self.host + "/DbXmlInfo.xml"
            try:
                with urllib.request.urlopen(url) as xmlfile:
                    xml_db = xmlfile.read()
                    loaded_from = "repeater"
                    _LOGGER.debug("Loaded XML database from repeater: %s", url)
                    if cache_path and not refresh_data:
                        if xml_db is not None:
                            with Path(cache_path).open("wb") as f:  # pylint: disable=unspecified-encoding
                                f.write(xml_db)
                                _LOGGER.info("Stored db as %s", cache_path)
            except Exception as e:
                _LOGGER.error("Failed to load XML database from %s: %s", url, e)
                raise

        _LOGGER.info("Loaded xml db from %s", loaded_from)

        parser = LutronXmlDbParser(
            xml_db_str=xml_db,
            variable_ids=variable_ids,
            controller=self,  # Pass controller to parser
        )
        assert parser.parse()  # throw our own exception
        self.areas = parser.areas
        self.name = parser.project_name
        self.variables = parser.variables
        self.guid = parser.lutron_guid

        _LOGGER.info("Found Lutron project: %s, %d areas", self.name, len(self.areas))

        if cache_path and loaded_from == "repeater":
            if xml_db is not None:
                with Path(cache_path).open("wb") as f:  # pylint: disable=unspecified-encoding
                    f.write(xml_db)

        return True
