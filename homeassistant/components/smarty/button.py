"""Platform to control a Salda Smarty XP/XV ventilation unit."""

from __future__ import annotations

import logging
from typing import Any

from pysmarty2 import Smarty

from homeassistant.components.button import ButtonEntity
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType

from . import DOMAIN, SIGNAL_UPDATE_SMARTY

_LOGGER = logging.getLogger(__name__)


async def async_setup_platform(
    hass: HomeAssistant,
    config: ConfigType,
    async_add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None,
) -> None:
    """Set up the Smarty Button Platform."""
    smarty: Smarty = hass.data[DOMAIN]["api"]
    name: str = f"{hass.data[DOMAIN]["name"]} Reset Filter Days Left"

    async_add_entities([SmartyResetFilterDaysLeftButton(name, smarty)], True)


class SmartyResetFilterDaysLeftButton(ButtonEntity):
    """Representation of a Smarty Button."""

    _attr_has_entity_name = True

    def __init__(self, name, smarty) -> None:
        """Initialize the entity."""
        self._attr_name = name
        self._smarty = smarty

    def press(self, **kwargs: Any) -> None:
        """Reset Filter Days Left."""
        self._smarty.reset_filters_timer()

    async def async_added_to_hass(self) -> None:
        """Call to update button."""
        self.async_on_remove(
            async_dispatcher_connect(
                self.hass, SIGNAL_UPDATE_SMARTY, self._update_callback
            )
        )

    @callback
    def _update_callback(self) -> None:
        """Call update method."""
        _LOGGER.debug("Updating state")
        self.async_write_ha_state()
