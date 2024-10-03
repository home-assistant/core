"""Platform to control a Salda Smarty XP/XV ventilation unit."""

from __future__ import annotations

import logging
from typing import Any

from pysmarty2 import Smarty

from homeassistant.components.switch import SwitchEntity
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
    """Set up the Smarty Fan Platform."""
    smarty: Smarty = hass.data[DOMAIN]["api"]
    name: str = f"{hass.data[DOMAIN]["name"]} Boost"

    async_add_entities([SmartyBoostSwitch(name, smarty)], True)


class SmartyBoostSwitch(SwitchEntity):
    """Representation of a Smarty Switch."""

    _attr_has_entity_name = True

    def __init__(self, name, smarty) -> None:
        """Initialize the entity."""
        self._is_on = False
        # self._attr_device_info = ...  # For automatic device registration
        # self._attr_unique_id = ...
        self._attr_name = name
        self._smarty = smarty

    @property
    def is_on(self) -> bool:
        """If the switch is currently on or off."""
        return bool(self._smarty.boost)
        # return self._is_on

    def turn_on(self, **kwargs: Any) -> None:
        """Turn the switch on."""
        self._is_on = True
        self._smarty.enable_boost()

    def turn_off(self, **kwargs: Any) -> None:
        """Turn the switch off."""
        self._is_on = False
        self._smarty.disable_boost()

    async def async_added_to_hass(self) -> None:
        """Call to update fan."""
        self.async_on_remove(
            async_dispatcher_connect(
                self.hass, SIGNAL_UPDATE_SMARTY, self._update_callback
            )
        )

    @callback
    def _update_callback(self) -> None:
        """Call update method."""
        _LOGGER.debug("Updating state")
        self._is_on = self._smarty.boost
        self.async_write_ha_state()
