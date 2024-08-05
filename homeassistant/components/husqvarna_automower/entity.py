"""Platform for Husqvarna Automower base entity."""

import asyncio
from collections.abc import Awaitable, Callable, Coroutine
import functools
import logging
from typing import Any

from aioautomower.exceptions import ApiException
from aioautomower.model import MowerActivities, MowerAttributes, MowerStates

from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import AutomowerDataUpdateCoordinator
from .const import DOMAIN, EXECUTION_TIME_DELAY

_LOGGER = logging.getLogger(__name__)

ERROR_ACTIVITIES = (
    MowerActivities.STOPPED_IN_GARDEN,
    MowerActivities.UNKNOWN,
    MowerActivities.NOT_APPLICABLE,
)
ERROR_STATES = [
    MowerStates.FATAL_ERROR,
    MowerStates.ERROR,
    MowerStates.ERROR_AT_POWER_UP,
    MowerStates.NOT_APPLICABLE,
    MowerStates.UNKNOWN,
    MowerStates.STOPPED,
    MowerStates.OFF,
]


def handle_sending_exception(
    poll_after_sending: bool = False,
) -> Callable[
    [Callable[..., Awaitable[Any]]], Callable[..., Coroutine[Any, Any, None]]
]:
    """Handle exceptions while sending a command and optionally refresh coordinator."""

    def decorator(
        func: Callable[..., Awaitable[Any]],
    ) -> Callable[..., Coroutine[Any, Any, None]]:
        @functools.wraps(func)
        async def wrapper(self: Any, *args: Any, **kwargs: Any) -> Any:
            try:
                await func(self, *args, **kwargs)
            except ApiException as exception:
                raise HomeAssistantError(
                    translation_domain=DOMAIN,
                    translation_key="command_send_failed",
                    translation_placeholders={"exception": str(exception)},
                ) from exception
            else:
                if poll_after_sending:
                    # As there are no updates from the websocket for this attribute,
                    # we need to wait until the command is executed and then poll the API.
                    await asyncio.sleep(EXECUTION_TIME_DELAY)
                    await self.coordinator.async_request_refresh()

        return wrapper

    return decorator


class AutomowerBaseEntity(CoordinatorEntity[AutomowerDataUpdateCoordinator]):
    """Defining the Automower base Entity."""

    _attr_has_entity_name = True

    def __init__(
        self,
        mower_id: str,
        coordinator: AutomowerDataUpdateCoordinator,
    ) -> None:
        """Initialize AutomowerEntity."""
        super().__init__(coordinator)
        self.mower_id = mower_id
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, mower_id)},
            manufacturer="Husqvarna",
            model=self.mower_attributes.system.model,
            name=self.mower_attributes.system.name,
            serial_number=self.mower_attributes.system.serial_number,
            suggested_area="Garden",
        )

    @property
    def mower_attributes(self) -> MowerAttributes:
        """Get the mower attributes of the current mower."""
        return self.coordinator.data[self.mower_id]


class AutomowerAvailableEntity(AutomowerBaseEntity):
    """Replies available when the mower is connected."""

    @property
    def available(self) -> bool:
        """Return True if the device is available."""
        return super().available and self.mower_attributes.metadata.connected


class AutomowerControlEntity(AutomowerAvailableEntity):
    """Replies available when the mower is connected and not in error state."""

    @property
    def available(self) -> bool:
        """Return True if the device is available."""
        return super().available and (
            self.mower_attributes.mower.state not in ERROR_STATES
            or self.mower_attributes.mower.activity not in ERROR_ACTIVITIES
        )
