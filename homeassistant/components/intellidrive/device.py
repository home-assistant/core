"""The hub to communicate with reisinger intellidrive devices."""

from __future__ import annotations

import asyncio
import logging
from typing import Any

import aiohttp
import async_timeout

_LOGGER = logging.getLogger(__name__)


class ReisingerSlidingDoorDeviceApi:
    """The api object for communication with reisinger slidingdoor api."""

    _retrievedData: Any

    def __init__(self, host: str, token: str, websession=None, **kwargs) -> None:
        """Initialize the slidingdoor device."""
        self._host = host
        self._token = token
        self._timeout = 500
        if websession is None:

            async def _create_session():
                _LOGGER.error("Creating session")
                return aiohttp.ClientSession()

            loop = asyncio.get_event_loop()
            self.websession = loop.run_until_complete(_create_session())
        else:
            self.websession = websession

    async def async_open(self, *args, **kwargs) -> None:
        """Operates the door: sends the open command.

        :return: None.
        """
        await self._async_operate("door/open", *args, **kwargs)

    async def async_close(self, *args, **kwargs) -> None:
        """Operates the door: sends the close command.

        :return: None.
        """
        await self._async_operate("door/close", *args, **kwargs)

    async def async_stop_door(self, *args, **kwargs) -> None:
        """Operate the door: sends the close command.

        :return: None.
        """
        await self._async_operate("door/stop", *args, **kwargs)

    def get_is_open(self, *args, **kwargs) -> bool | None:
        """Get the current door-open status. Returns True if the given door is open, False otherwise.

        :return: False if the door is closed, True otherwise.
        """
        # self.check_full_update_done()
        # target_channel = self._get_default_channel_index(channel)
        # return self._door_open_state_by_channel.get(target_channel, None)
        return False

    async def authenticate(self) -> bool:
        """Test if we can authenticate with the host."""
        return True

    async def _async_operate(self, command: str, *args, **kwargs) -> None:
        """Operates the door: sends the commands to api.

        :param command: the command to operate: defaults to 0
        :return: None.
        """
        return None

    async def async_update_state(self) -> dict[str, Any]:
        """Update the door: Retrieves the device vcalues.

        :return: Datas from device.
        """
        return await self._execute("door/state")

        # return cast(dict[str, Any], self._retrievedData.dict())

    async def _execute(self, command, retry=2):
        """Execute command."""
        url = f"{self._host}/{command}"
        try:
            async with async_timeout.timeout(self._timeout):
                resp = await self.websession.get(url)
            if resp.status != 200:
                _LOGGER.error(
                    "Error connecting to Reisinger Drive, resp code: %s", resp.status
                )
                return None
            result = await resp.json(content_type=None)
        except aiohttp.ClientError as err:
            if retry > 0:
                return await self._execute(command, retry - 1)
            _LOGGER.error(
                "Error connecting to Reisinger Drive: %s ", err, exc_info=True
            )
            raise
        except asyncio.TimeoutError:
            if retry > 0:
                return await self._execute(command, retry - 1)
            _LOGGER.error("Timed out when connecting to Reisinger Drive device")
            raise

        return result
