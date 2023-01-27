"""The hub to communicate with reisinger intellidrive devices."""

from __future__ import annotations

import logging

_LOGGER = logging.getLogger(__name__)


class ReisingerSlidingDoorDevice:
    """
    A `BaseDevice` is a generic representation of a Meross device.

    Any BaseDevice is characterized by some generic information, such as user's defined
    name, type (i.e. device specific model), firmware/hardware version, a Meross internal
    identifier, a library assigned internal identifier.
    """

    def __init__(self, host: str, token: str, **kwargs):
        """Initialize the slidingdoor device."""
        self._host = host
        self._token = token

    async def async_open(self, *args, **kwargs) -> None:
        """
        Operates the door: sends the open command.

        :return: None.
        """
        await self._async_operate("door/open", *args, **kwargs)

    async def async_close(self, *args, **kwargs) -> None:
        """
        Operates the door: sends the close command.

        :return: None.
        """
        await self._async_operate("door/close", *args, **kwargs)

    async def async_stop_door(self, *args, **kwargs) -> None:
        """
        Operate the door: sends the close command.

        :return: None.
        """
        await self._async_operate("stop", *args, **kwargs)

    def get_is_open(self, *args, **kwargs) -> bool | None:
        """
        Get the current door-open status. Returns True if the given door is open, False otherwise.

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
        """
        Operates the door: sends the commands to api.

        :param command: the command to operate: defaults to 0
        :return: None.
        """
        return None
