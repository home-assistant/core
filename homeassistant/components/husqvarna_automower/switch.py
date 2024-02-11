"""Creates a switch entity for the mower."""
import logging

from aioautomower.exceptions import ApiException
from aioautomower.model import MowerStates, RestrictedReasons

from homeassistant.components.switch import SwitchEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from .coordinator import AutomowerDataUpdateCoordinator
from .entity import AutomowerBaseEntity

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up switch platform."""
    coordinator: AutomowerDataUpdateCoordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities(
        AutomowerSwitchEntity(mower_id, coordinator) for mower_id in coordinator.data
    )


class AutomowerSwitchEntity(AutomowerBaseEntity, SwitchEntity):
    """Defining the Automower switch."""

    _attr_translation_key = "park_until_further_notice"

    def __init__(
        self,
        mower_id: str,
        coordinator: AutomowerDataUpdateCoordinator,
    ) -> None:
        """Set up Automower switch."""
        super().__init__(mower_id, coordinator)
        self._attr_unique_id = f"{self.mower_id}_park_until_further_notice"

    @property
    def is_on(self) -> bool:
        """Return the state of the switch."""
        attributes = self.mower_attributes
        return (
            attributes.mower.state == MowerStates.RESTRICTED
            and attributes.planner.restricted_reason == RestrictedReasons.NOT_APPLICABLE
        )

    async def async_turn_on(self):
        """Turn the entity on."""
        try:
            await self.coordinator.api.park_until_further_notice(self.mower_id)
        except ApiException as exception:
            raise HomeAssistantError(
                f"Command couldn't be sent to the command queue: {exception}"
            ) from exception

    async def async_turn_off(self):
        """Turn the entity on."""
        try:
            await self.coordinator.api.resume_schedule(self.mower_id)
        except ApiException as exception:
            raise HomeAssistantError(
                f"Command couldn't be sent to the command queue: {exception}"
            ) from exception
