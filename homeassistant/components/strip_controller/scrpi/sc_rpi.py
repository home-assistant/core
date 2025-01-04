"""Based on Based on [WLED API Client for Python](https://pypi.org/project/wled/).

GitHub repo: https://github.com/frenck/python-wled.
"""

from dataclasses import dataclass
from logging import getLogger

import aiohttp

from .commands import Command, Status as CmdStatus
from .exceptions import ScRpiEmptyResponseError
from .models import Device

LOGGER = getLogger(__package__)


class ScRpiError(Exception):
    """Generic ScRpi exception."""


@dataclass
class ScRpiClient:
    """Provides operations to invoke on a Strip Controller device.

    Operations are sent as JSON objects through websocket (instead of HTTP request as in
    [request](https://github.com/frenck/python-wled/blob/b4e626b5a7ed9e2daff0049e556e7e577e41dc8b/src/wled/wled.py#L141)
    method of WLED). Then, information is received and processed asynchronously in `listen` method.
    """

    url: str

    session: aiohttp.client.ClientSession

    _client: aiohttp.ClientWebSocketResponse | None = None

    _device: Device | None = None

    def __init__(self, url: str, session: aiohttp.ClientSession) -> None:
        """Initialize the client."""
        self.url = url
        self.session = session
        # Hardcoded for testing, see TOD comments
        self.section_map = {0: {"is_on": False}}

    # TOD: think how to handle different cases, for example when section_id is not on the map , section is not on device, etc

    # Maybe invoking an update method which initially collect sections and all its attributes from device

    # TOD: think cases when color is None

    # TOD: implement a listen method like https://github.com/frenck/python-wled/blob/b4e626b5a7ed9e2daff0049e556e7e577e41dc8b/src/wled/wled.py#L93

    # TOD: implement update method like

    async def section(self, is_on, section_id: int, color) -> None:
        """Define a section on the strip."""
        if self.section_map[section_id] != is_on:
            cmd = Command("turn_on")

        if cmd is not None:
            LOGGER.debug("Sending command %s to ScRpi device", cmd)
            await self._send_command(cmd)

    @property
    def connected(self) -> bool:
        """Return if we are connect to the WebSocket of a ScRpi device.

        Returns
        -------
            True if we are connected to the WebSocket of a ScRpi device,
            False otherwise.

        """
        return self._client is not None and not self._client.closed

    async def connect(self):
        """Establish websocket connection."""
        if self.connected:
            return

        self._client = await self.session.ws_connect(url=self.url)

    async def update(self) -> Device:
        """Get all information about the device in a single call.

        This method updates all ScRpi information available with a single API call.

        Returns
        -------
            ScRpi Device data.

        Raises
        ------
            ScRpiEmptyResponseError: The ScRpi device returned an empty response.

        """
        if not (data := await self._send_command(CmdStatus())):
            msg = (
                f"ScRpi device at {self.url} returned an empty API"
                " response on full update",
            )
            raise ScRpiEmptyResponseError(msg)

        if not self._device:
            self._device = Device.from_dict(data)
        else:
            self._device.update_from_dict(data)

        return self._device

    async def _send_command(self, cmd: Command):
        """Send command to device."""
        if self._client is None or not self._client.closed:
            LOGGER.debug("Connecting ScRpi client")
            await self.connect()

        if self._client is not None:
            cmd_as_json = cmd.to_json()
            LOGGER.debug("Sending command %s", cmd_as_json)
            await self._client.send_json(cmd_as_json)
        else:
            raise ScRpiError("Client is still None after attempting to connect")
