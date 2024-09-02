"""Sensor platform for the Flipr's Hub."""

import logging

from homeassistant.components.select import SelectEntity, SelectEntityDescription
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import CONF_ENTRY_HUB_COORDINATORS, DOMAIN
from .entity import FliprEntity

_LOGGER = logging.getLogger(__name__)

SELECT_TYPES: tuple[SelectEntityDescription, ...] = (
    SelectEntityDescription(
        key="hubMode",
        translation_key="hub_mode",
        options=["auto", "manual", "planning"],
    ),
)


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up select for Flipr hub mode."""
    coordinators = hass.data[DOMAIN][CONF_ENTRY_HUB_COORDINATORS]

    for coordinator in coordinators:
        async_add_entities(
            HubSwitch(coordinator, description, True) for description in SELECT_TYPES
        )


class HubSwitch(FliprEntity, SelectEntity):
    """Select representing Hub mode."""

    @property
    def current_option(self) -> str | None:
        """Return current select option."""
        return self.coordinator.data["mode"]

    async def async_select_option(self, option: str) -> None:
        """Select new mode for Hub."""
        _LOGGER.debug("Changing mode of %s to %s", self.device_id, option)
        data = await self.hass.async_add_executor_job(
            self.coordinator.client.set_hub_mode,  # type: ignore[attr-defined]
            self.device_id,
            option,
        )
        _LOGGER.debug("New hub infos are %s", data)
        self.coordinator.async_set_updated_data(data)
