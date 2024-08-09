"""Module providing services for SwitchBotAPI integration."""

from collections.abc import Callable, Coroutine
from logging import getLogger
from typing import Any

from switchbot_api import SwitchBotAPI

from homeassistant.core import ServiceCall
from homeassistant.util.json import JsonObjectType

from .const import (
    ATTR_COMMAND,
    ATTR_COMMAND_PARAMETER,
    ATTR_COMMAND_TYPE,
    ATTR_UNIQUE_ID,
)

_LOGGER = getLogger(__name__)
_DEFAULT_PARAMETER = "default"


def make_list_devices(
    api: SwitchBotAPI,
) -> Callable[[ServiceCall], Coroutine[Any, Any, JsonObjectType]]:
    """List devices."""

    async def list_devices(_: ServiceCall) -> JsonObjectType:
        """List devices."""
        devices = await api.list_devices()
        return {
            "items": [
                {
                    "unique_id": device.device_id,
                    "device_name": device.device_name,
                    "device_type": device.device_type,
                }
                for device in devices
            ]
        }

    return list_devices


def make_send_command_service(
    api: SwitchBotAPI,
) -> Callable[[ServiceCall], Coroutine[Any, Any, None]]:
    """Create a command service for SwitchBotAPI."""

    async def send_command_service(call: ServiceCall) -> None:
        """Handle the service call."""
        unique_id = call.data.get(ATTR_UNIQUE_ID)
        command_type = call.data.get(ATTR_COMMAND_TYPE)
        command = call.data.get(ATTR_COMMAND)
        parameter = call.data.get(ATTR_COMMAND_PARAMETER, _DEFAULT_PARAMETER)
        _LOGGER.debug(
            "Sending command to %s: %s %s %s",
            unique_id,
            command_type,
            command,
            parameter,
        )
        await api.send_command(unique_id, command, command_type, parameter)

    return send_command_service
