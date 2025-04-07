"""Switch platform for the Flipr's Hub."""

import logging
from typing import Any

from homeassistant.components.switch import SwitchEntity, SwitchEntityDescription
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .coordinator import FliprConfigEntry
from .entity import FliprEntity

_LOGGER = logging.getLogger(__name__)

SWITCH_TYPES: tuple[SwitchEntityDescription, ...] = (
    SwitchEntityDescription(
        key="hubState",
        name=None,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: FliprConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up switch for Flipr hub."""
    coordinators = config_entry.runtime_data.hub_coordinators

    async_add_entities(
        FliprHubSwitch(coordinator, description, True)
        for description in SWITCH_TYPES
        for coordinator in coordinators
    )


class FliprHubSwitch(FliprEntity, SwitchEntity):
    """Switch representing Hub state."""

    @property
    def is_on(self) -> bool:
        """Return state of the switch."""
        _LOGGER.debug("coordinator data = %s", self.coordinator.data)
        return self.coordinator.data["state"]

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn off the switch."""
        _LOGGER.debug("Switching off %s", self.device_id)
        data = await self.hass.async_add_executor_job(
            self.coordinator.client.set_hub_state,
            self.device_id,
            False,
        )
        _LOGGER.debug("New hub infos are %s", data)
        self.coordinator.async_set_updated_data(data)

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn on the switch."""
        _LOGGER.debug("Switching on %s", self.device_id)
        data = await self.hass.async_add_executor_job(
            self.coordinator.client.set_hub_state,
            self.device_id,
            True,
        )
        _LOGGER.debug("New hub infos are %s", data)
        self.coordinator.async_set_updated_data(data)
