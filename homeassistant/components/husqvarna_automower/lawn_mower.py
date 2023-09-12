"""Husqvarna automower entity."""
import logging

from aioautomower import AutomowerSession, MowerActivities, MowerStates

from homeassistant.components.lawn_mower import (
    LawnMowerActivity,
    LawnMowerEntity,
    LawnMowerEntityFeature,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from .coordinator import AutomowerDataUpdateCoordinator
from .entity import AutomowerEntity

SUPPORT_STATE_SERVICES = (
    LawnMowerEntityFeature.DOCK
    | LawnMowerEntityFeature.PAUSE
    | LawnMowerEntityFeature.START_MOWING
)

DOCKED_ACTIVITIES = (MowerActivities.PARKED_IN_CS, MowerActivities.CHARGING)
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
        HusqvarnaAutomowerEntity(coordinator, idx)
        for idx, ent in enumerate(coordinator.session.data["data"])
    )


class HusqvarnaAutomowerEntity(LawnMowerEntity, AutomowerEntity):
    """Defining each mower Entity."""

    _attr_name = None
    _attr_supported_features = SUPPORT_STATE_SERVICES

    def __init__(self, session: AutomowerSession, idx: int) -> None:
        """Set up HusqvarnaAutomowerEntity."""
        super().__init__(session, idx)
        self._attr_unique_id = (
            f"{self.coordinator.session.api_key}_{self.mower_id}_lawn_mower"
        )

    @property
    def available(self) -> bool:
        """Return True if the device is available."""
        return self.mower_attributes.metadata.connected

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
        activity = LawnMowerActivity.ERROR
        if not (
            (mower_attributes.mower.state in ERROR_STATES)
            or mower_attributes.mower.activity in ERROR_ACTIVITIES
        ):
            _LOGGER.warning(
                "Unknown activity detected. Mower state is %s and mower activity is %s. \
                Please report this issue",
                mower_attributes.mower.state,
                mower_attributes.mower.activity,
            )
        return LawnMowerActivity(activity)

    @property
    def extra_state_attributes(self) -> dict:
        """Return the specific state attributes of this mower."""
        action = self.mower_attributes.planner.override.action
        action = action.lower() if action is not None else action
        return {
            "action": action,
        }

    async def async_start_mowing(self) -> None:
        """Resume schedule."""
        await self.coordinator.session.resume_schedule(self.mower_id)

    async def async_pause(self) -> None:
        """Pauses the mower."""
        await self.coordinator.session.pause_mowing(self.mower_id)

    async def async_dock(self) -> None:
        """Parks the mower until next schedule."""
        await self.coordinator.session.park_until_next_schedule(self.mower_id)
