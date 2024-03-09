"""Husqvarna Automower lawn mower entity."""

import logging

from aioautomower.exceptions import ApiException
from aioautomower.model import MowerActivities, MowerStates

from homeassistant.components.lawn_mower import (
    LawnMowerActivity,
    LawnMowerEntity,
    LawnMowerEntityFeature,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from .coordinator import AutomowerDataUpdateCoordinator
from .entity import AutomowerControlEntity

SUPPORT_STATE_SERVICES = (
    LawnMowerEntityFeature.DOCK
    | LawnMowerEntityFeature.PAUSE
    | LawnMowerEntityFeature.START_MOWING
)

DOCKED_ACTIVITIES = (MowerActivities.PARKED_IN_CS, MowerActivities.CHARGING)
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


_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up lawn mower platform."""
    coordinator: AutomowerDataUpdateCoordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities(
        AutomowerLawnMowerEntity(mower_id, coordinator) for mower_id in coordinator.data
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

    async def async_start_mowing(self) -> None:
        """Resume schedule."""
        try:
            await self.coordinator.api.resume_schedule(self.mower_id)
        except ApiException as exception:
            raise HomeAssistantError(
                f"Command couldn't be sent to the command queue: {exception}"
            ) from exception

    async def async_pause(self) -> None:
        """Pauses the mower."""
        try:
            await self.coordinator.api.pause_mowing(self.mower_id)
        except ApiException as exception:
            raise HomeAssistantError(
                f"Command couldn't be sent to the command queue: {exception}"
            ) from exception

    async def async_dock(self) -> None:
        """Parks the mower until next schedule."""
        try:
            await self.coordinator.api.park_until_next_schedule(self.mower_id)
        except ApiException as exception:
            raise HomeAssistantError(
                f"Command couldn't be sent to the command queue: {exception}"
            ) from exception
