"""Client for Webex CE devices."""

from __future__ import annotations

from collections.abc import Callable
import logging
from typing import Any

import xows

_LOGGER = logging.getLogger(__name__)


class WebexCEClient:
    """Client for interacting with Cisco Webex CE devices."""

    def __init__(self, host: str, username: str, password: str) -> None:
        """Initialize the client."""
        self.host = host
        self.username = username
        self.password = password
        self._client: xows.XoWSClient | None = None
        self._callbacks: dict[str, tuple[list[str], Callable]] = {}

    async def connect(self) -> None:
        """Connect to the device."""
        client = xows.XoWSClient(
            self.host,
            username=self.username,
            password=self.password,
        )
        self._client = await client.__aenter__()  # pylint: disable=unnecessary-dunder-call

    async def disconnect(self) -> None:
        """Disconnect from the device."""
        if self._client:
            await self._client.__aexit__(None, None, None)
            self._client = None

    async def xget(self, path: list[str]) -> Any:
        """Get a status value from the device."""
        if not self._client:
            raise RuntimeError("Client not connected")
        return await self._client.xGet(path)

    async def xcommand(self, path: list[str], **params: Any) -> Any:
        """Execute a command on the device."""
        if not self._client:
            raise RuntimeError("Client not connected")
        return await self._client.xCommand(path, **params)

    async def subscribe_feedback(
        self, feedback_id: str, path: list[str], callback: Callable
    ) -> None:
        """Subscribe to feedback for a specific status path."""
        if not self._client:
            raise RuntimeError("Client not connected")

        # Store callback info for resubscription if needed
        self._callbacks[feedback_id] = (path, callback)

        # Subscribe with initial update
        await self._client.subscribe(path, callback, notify_current_value=True)

    async def subscribe_ui_events(self, callback: Callable) -> None:
        """Subscribe to UI extension events."""
        if not self._client:
            raise RuntimeError("Client not connected")

        # Subscribe to UserInterface Extensions Widget Action events
        await self._client.subscribe_event(
            "UserInterface Extensions Widget Action", callback
        )

    async def get_serial_number(self) -> str:
        """Get the device serial number."""
        result = await self.xget(
            ["Status", "SystemUnit", "Hardware", "Module", "SerialNumber"]
        )
        # Handle the response structure - it might be a dict or direct value
        if isinstance(result, dict):
            return str(result.get("SerialNumber", ""))
        return str(result)

    async def get_device_info(self) -> dict[str, str]:
        """Get device information for device registry."""
        try:
            # Get device name from ContactInfo
            device_name = await self.xget(
                ["Status", "UserInterface", "ContactInfo", "Name"]
            )
            product_info = await self.xget(["Status", "SystemUnit", "ProductId"])
            software_info = await self.xget(
                ["Status", "SystemUnit", "Software", "Version"]
            )
            serial = await self.get_serial_number()

            return {
                "name": str(device_name) if device_name else "Webex Device",
                "serial": serial,
                "product": str(product_info),
                "software_version": str(software_info),
            }
        except Exception as err:
            _LOGGER.error("Failed to get device info: %s", err)
            raise
