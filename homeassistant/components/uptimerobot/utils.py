"""Utility functions for the UptimeRobot integration."""

from collections.abc import Awaitable, Callable, Coroutine
from functools import wraps
from typing import Any, Concatenate

from pyuptimerobot import (
    UptimeRobotAuthenticationException,
    UptimeRobotException,
    UptimeRobotMonitor,
)

from homeassistant.exceptions import HomeAssistantError

from .const import DOMAIN
from .coordinator import UptimeRobotDataUpdateCoordinator
from .entity import UptimeRobotEntity


def uptimerobot_api_call[_T: UptimeRobotEntity, **_P](
    func: Callable[Concatenate[_T, _P], Awaitable[None]],
) -> Callable[Concatenate[_T, _P], Coroutine[Any, Any, None]]:
    """Catch UptimeRobot API call exceptions."""

    @wraps(func)
    async def cmd_wrapper(self: _T, *args: _P.args, **kwargs: _P.kwargs) -> None:
        """Wrap all command methods."""
        try:
            await func(self, *args, **kwargs)
        except UptimeRobotAuthenticationException:
            self.coordinator.config_entry.async_start_reauth(self.hass)
            return
        except UptimeRobotException as exception:
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="api_switch_exception",
                translation_placeholders={"error": "Generic UptimeRobot exception"},
            ) from exception

    return cmd_wrapper


def new_device_listener(
    coordinator: UptimeRobotDataUpdateCoordinator,
    new_devices_callback: Callable[[list[UptimeRobotMonitor]], None],
) -> Callable[[], None]:
    """Subscribe to coordinator updates to check for new devices."""
    known_devices: set[int] = set()

    def _check_devices() -> None:
        """Check for new devices and call callback with any new monitors."""
        new_ids = coordinator.data.keys() - known_devices
        if new_ids:
            known_devices.update(new_ids)
            new_devices_callback([coordinator.data[i] for i in new_ids])

    # Check for devices immediately
    _check_devices()

    return coordinator.async_add_listener(_check_devices)
