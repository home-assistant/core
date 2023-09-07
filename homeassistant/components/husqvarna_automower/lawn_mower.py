"""Husqvarna automower entity."""
import logging

from aioautomower import AutomowerSession
from aiohttp import ClientResponseError

from homeassistant.components.lawn_mower import (
    LawnMowerActivity,
    LawnMowerEntity,
    LawnMowerEntityFeature,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import (
    DOCKED_STATES,
    DOMAIN,
    ERROR_ACTIVITIES,
    ERROR_STATES,
    MOWING_STATES,
    PAUSED_STATES,
)
from .entity import AutomowerEntity

SUPPORT_STATE_SERVICES = (
    LawnMowerEntityFeature.DOCK
    | LawnMowerEntityFeature.PAUSE
    | LawnMowerEntityFeature.START_MOWING
)


_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up lawn mower platform."""
    coordinator = hass.data[DOMAIN][entry.entry_id]
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
        self._attr_unique_id = self.coordinator.session.data["data"][self.idx]["id"]

    @property
    def available(self) -> bool:
        """Return True if the device is available."""
        return self.mower_attributes["metadata"]["connected"]

    @property
    def activity(self) -> LawnMowerActivity:
        """Return the state of the mower."""
        mower_attributes = self.mower_attributes
        if mower_attributes["mower"]["state"] in PAUSED_STATES:
            return LawnMowerActivity.PAUSED
        if mower_attributes["mower"]["activity"] in MOWING_STATES:
            return LawnMowerActivity.MOWING
        if (mower_attributes["mower"]["state"] == "RESTRICTED") or (
            mower_attributes["mower"]["activity"] in DOCKED_STATES
        ):
            return LawnMowerActivity.DOCKED
        activity = LawnMowerActivity.ERROR
        if not (
            (mower_attributes["mower"]["state"] in ERROR_STATES)
            or mower_attributes["mower"]["activity"] in ERROR_ACTIVITIES
        ):
            _LOGGER.warning(
                "Unknown activity detected. Mower state is %s and mower activity is %s. \
                Please report this issue",
                mower_attributes["mower"]["state"],
                mower_attributes["mower"]["activity"],
            )
        return LawnMowerActivity(activity)

    @property
    def extra_state_attributes(self) -> dict:
        """Return the specific state attributes of this mower."""
        action = self.mower_attributes["planner"]["override"]["action"]
        action = action.lower() if action is not None else action
        return {
            "action": action,
        }

    async def async_start_mowing(self) -> None:
        """Resume schedule."""
        command_type = "actions"
        payload = '{"data": {"type": "ResumeSchedule"}}'
        try:
            await self.coordinator.session.action(self.mower_id, payload, command_type)
        except ClientResponseError as exception:
            _LOGGER.error("Command couldn't be sent to the command que: %s", exception)

    async def async_pause(self) -> None:
        """Pauses the mower."""
        command_type = "actions"
        payload = '{"data": {"type": "Pause"}}'
        try:
            await self.coordinator.session.action(self.mower_id, payload, command_type)
        except ClientResponseError as exception:
            _LOGGER.error("Command couldn't be sent to the command que: %s", exception)

    async def async_dock(self) -> None:
        """Parks the mower until next schedule."""
        command_type = "actions"
        payload = '{"data": {"type": "ParkUntilNextSchedule"}}'
        try:
            await self.coordinator.session.action(self.mower_id, payload, command_type)
        except ClientResponseError as exception:
            _LOGGER.error("Command couldn't be sent to the command que: %s", exception)
