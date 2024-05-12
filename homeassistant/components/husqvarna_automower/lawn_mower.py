"""Husqvarna Automower lawn mower entity."""

from collections.abc import Awaitable, Callable, Coroutine
import functools
import logging
from typing import Any

from aioautomower.exceptions import ApiException
from aioautomower.model import MowerActivities, MowerStates
import voluptuous as vol

from homeassistant.components.lawn_mower import (
    LawnMowerActivity,
    LawnMowerEntity,
    LawnMowerEntityFeature,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import entity_platform
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from .coordinator import AutomowerDataUpdateCoordinator
from .entity import AutomowerControlEntity

DOCKED_ACTIVITIES = (MowerActivities.PARKED_IN_CS, MowerActivities.CHARGING)
EXCEPTION_TEXT = "Failed to send command: {exception}"
MOWING_ACTIVITIES = (
    MowerActivities.MOWING,
    MowerActivities.LEAVING,
    MowerActivities.GOING_HOME,
)
PAUSED_STATES = [
    MowerStates.PAUSED,
    MowerStates.WAIT_UPDATING,
    MowerStates.WAIT_POWER_UP,
]
SUPPORT_STATE_SERVICES = (
    LawnMowerEntityFeature.DOCK
    | LawnMowerEntityFeature.PAUSE
    | LawnMowerEntityFeature.START_MOWING
)

_LOGGER = logging.getLogger(__name__)


def handle_sending_exception(
    func: Callable[..., Awaitable[Any]],
) -> Callable[..., Coroutine[Any, Any, None]]:
    """Handle exceptions while sending a command."""

    @functools.wraps(func)
    async def wrapper(self: Any, *args: Any, **kwargs: Any) -> Any:
        try:
            return await func(self, *args, **kwargs)
        except ApiException as exception:
            raise HomeAssistantError(
                EXCEPTION_TEXT.format(exception=exception)
            ) from exception

    return wrapper


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up lawn mower platform."""
    coordinator: AutomowerDataUpdateCoordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities(
        AutomowerLawnMowerEntity(mower_id, coordinator) for mower_id in coordinator.data
    )

    platform = entity_platform.async_get_current_platform()
    platform.async_register_entity_service(
        "start_for",
        {
            vol.Required("duration"): vol.Coerce(int),
        },
        "async_start_for",
    )

    platform.async_register_entity_service(
        "park_for",
        {
            vol.Required("duration"): vol.Coerce(int),
        },
        "async_park_for",
    )


class AutomowerLawnMowerEntity(AutomowerControlEntity, LawnMowerEntity):
    """Defining each mower Entity."""

    _attr_name = None
    _attr_supported_features = SUPPORT_STATE_SERVICES

    def __init__(
        self,
        mower_id: str,
        coordinator: AutomowerDataUpdateCoordinator,
    ) -> None:
        """Set up HusqvarnaAutomowerEntity."""
        super().__init__(mower_id, coordinator)
        self._attr_unique_id = mower_id

    @property
    def activity(self) -> LawnMowerActivity:
        """Return the state of the mower."""
        mower_attributes = self.mower_attributes
        if mower_attributes.mower.state in PAUSED_STATES:
            return LawnMowerActivity.PAUSED
        if mower_attributes.mower.activity in MOWING_ACTIVITIES:
            return LawnMowerActivity.MOWING
        if (mower_attributes.mower.state == "RESTRICTED") or (
            mower_attributes.mower.activity in DOCKED_ACTIVITIES
        ):
            return LawnMowerActivity.DOCKED
        return LawnMowerActivity.ERROR

    @handle_sending_exception
    async def async_start_mowing(self) -> None:
        """Resume schedule."""
        await self.coordinator.api.commands.resume_schedule(self.mower_id)

    @handle_sending_exception
    async def async_pause(self) -> None:
        """Pauses the mower."""
        await self.coordinator.api.commands.pause_mowing(self.mower_id)

    @handle_sending_exception
    async def async_dock(self) -> None:
        """Parks the mower until next schedule."""
        await self.coordinator.api.commands.park_until_next_schedule(self.mower_id)

    @handle_sending_exception
    async def async_start_for(self, duration: int) -> None:
        """Let the mower mow for a given time."""
        await self.coordinator.api.commands.start_for(self.mower_id, duration)

    @handle_sending_exception
    async def async_park_for(self, duration: int) -> None:
        """Let the mower park for a given time."""
        await self.coordinator.api.commands.park_for(self.mower_id, duration)
