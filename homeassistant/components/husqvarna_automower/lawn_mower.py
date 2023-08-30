"""Creates a vacuum entity for the mower."""
import logging

from aiohttp import ClientResponseError

from homeassistant.components.lawn_mower import (
    LawnMowerActivity,
    LawnMowerEntity,
    LawnMowerEntityFeature,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_platform
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN, ERROR_ACTIVITIES
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
    """Set up vacuum platform."""
    coordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities(
        HusqvarnaAutomowerEntity(coordinator, idx)
        for idx, ent in enumerate(coordinator.session.data["data"])
    )
    entity_platform.current_platform.get()


class HusqvarnaAutomowerEntity(LawnMowerEntity, AutomowerEntity):
    """Defining each mower Entity."""

    _attr_name: str | None = None
    _attr_supported_features = SUPPORT_STATE_SERVICES
    _attr_translation_key = "mower"

    def __init__(self, session, idx) -> None:
        """Set up HusqvarnaAutomowerEntity."""
        super().__init__(session, idx)
        self._attr_unique_id = self.coordinator.session.data["data"][self.idx]["id"]

    @property
    def available(self) -> bool:
        """Return True if the device is available."""
        available = self.get_mower_attributes()["metadata"]["connected"]
        return available

    @property
    def activity(self) -> LawnMowerActivity:
        """Return the state of the mower."""
        mower_attributes = AutomowerEntity.get_mower_attributes(self)
        if mower_attributes["mower"]["state"] in ["PAUSED"]:
            activity = LawnMowerActivity.PAUSED
        if mower_attributes["mower"]["state"] in [
            "WAIT_UPDATING",
            "WAIT_POWER_UP",
        ]:
            activity = LawnMowerActivity.PAUSED
        if mower_attributes["mower"]["activity"] in ["MOWING", "LEAVING"]:
            activity = LawnMowerActivity.MOWING
        if mower_attributes["mower"]["activity"] == "GOING_HOME":
            activity = LawnMowerActivity.MOWING
        if (mower_attributes["mower"]["state"] == "RESTRICTED") or (
            mower_attributes["mower"]["activity"] in ["PARKED_IN_CS", "CHARGING"]
        ):
            activity = LawnMowerActivity.DOCKED
        if (
            mower_attributes["mower"]["state"]
            in [
                "FATAL_ERROR",
                "ERROR",
                "ERROR_AT_POWER_UP",
                "NOT_APPLICABLE",
                "UNKNOWN",
                "STOPPED",
                "OFF",
            ]
        ) or mower_attributes["mower"]["activity"] in ERROR_ACTIVITIES:
            activity = LawnMowerActivity.ERROR
        return LawnMowerActivity(activity)

    @property
    def extra_state_attributes(self) -> dict:
        """Return the specific state attributes of this mower."""
        mower_attributes = AutomowerEntity.get_mower_attributes(self)
        action = mower_attributes["planner"]["override"]["action"]
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
