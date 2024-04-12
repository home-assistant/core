"""Creates a switch entity for the mower."""

import logging
from typing import Any

from aioautomower.exceptions import ApiException
from aioautomower.model import MowerActivities, MowerStates, RestrictedReasons

from homeassistant.components.switch import SwitchEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from .coordinator import AutomowerDataUpdateCoordinator
from .entity import AutomowerControlEntity

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


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up switch platform."""
    coordinator: AutomowerDataUpdateCoordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities(
        AutomowerSwitchEntity(mower_id, coordinator) for mower_id in coordinator.data
    )


class AutomowerSwitchEntity(AutomowerControlEntity, SwitchEntity):
    """Defining the Automower switch."""

    _attr_translation_key = "enable_schedule"

    def __init__(
        self,
        mower_id: str,
        coordinator: AutomowerDataUpdateCoordinator,
    ) -> None:
        """Set up Automower switch."""
        super().__init__(mower_id, coordinator)
        self._attr_unique_id = f"{self.mower_id}_{self._attr_translation_key}"

    @property
    def is_on(self) -> bool:
        """Return the state of the switch."""
        attributes = self.mower_attributes
        return not (
            attributes.mower.state == MowerStates.RESTRICTED
            and attributes.planner.restricted_reason == RestrictedReasons.NOT_APPLICABLE
        )

    @property
    def available(self) -> bool:
        """Return True if the device is available."""
        return super().available and (
            self.mower_attributes.mower.state not in ERROR_STATES
            or self.mower_attributes.mower.activity not in ERROR_ACTIVITIES
        )

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the entity off."""
        try:
            await self.coordinator.api.park_until_further_notice(self.mower_id)
        except ApiException as exception:
            raise HomeAssistantError(
                f"Command couldn't be sent to the command queue: {exception}"
            ) from exception

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the entity on."""
        try:
            await self.coordinator.api.resume_schedule(self.mower_id)
        except ApiException as exception:
            raise HomeAssistantError(
                f"Command couldn't be sent to the command queue: {exception}"
            ) from exception
