"""Switch platform for the Flipr's Hub."""

import logging
from typing import Any

from homeassistant.components.switch import SwitchEntity, SwitchEntityDescription
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import CONF_ENTRY_HUB_COORDINATORS, DOMAIN
from .entity import FliprEntity

_LOGGER = logging.getLogger(__name__)

SWITCH_TYPES: tuple[SwitchEntityDescription, ...] = (
    SwitchEntityDescription(
        key="hubState",
        translation_key="hub_state",
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up switch for Flipr hub."""
    coordinators = hass.data[DOMAIN][CONF_ENTRY_HUB_COORDINATORS]

    for coordinator in coordinators:
        async_add_entities(
            HubSwitch(coordinator, description, True) for description in SWITCH_TYPES
        )


class HubSwitch(FliprEntity, SwitchEntity):
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
            self.coordinator.client.set_hub_state,  # type: ignore[attr-defined]
            self.device_id,
            False,
        )
        _LOGGER.debug("New hub infos are %s", data)
        self.coordinator.async_set_updated_data(data)

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn on the switch."""
        _LOGGER.debug("Switching on %s", self.device_id)
        data = await self.hass.async_add_executor_job(
            self.coordinator.client.set_hub_state,  # type: ignore[attr-defined]
            self.device_id,
            True,
        )
        _LOGGER.debug("New hub infos are %s", data)
        self.coordinator.async_set_updated_data(data)
