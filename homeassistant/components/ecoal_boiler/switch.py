"""Allows to configuration ecoal (esterownik.pl) pumps as switches."""

from __future__ import annotations

from typing import Any

from homeassistant.components.switch import SwitchEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType

from . import AVAILABLE_PUMPS, DATA_ECOAL_BOILER


def setup_platform(
    hass: HomeAssistant,
    config: ConfigType,
    add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None,
) -> None:
    """Set up switches based on ecoal interface."""
    if discovery_info is None:
        return
    ecoal_contr = hass.data[DATA_ECOAL_BOILER]
    switches = []
    for pump_id in discovery_info:
        name = AVAILABLE_PUMPS[pump_id]
        switches.append(EcoalSwitch(ecoal_contr, name, pump_id))
    add_entities(switches, True)


class EcoalSwitch(SwitchEntity):
    """Representation of Ecoal switch."""

    def __init__(self, ecoal_contr, name, state_attr):
        """Initialize switch.

        Sets HA switch to state as read from controller.
        """
        self._ecoal_contr = ecoal_contr
        self._attr_name = name
        self._state_attr = state_attr
        # Ecoalcotroller holds convention that same postfix is used
        # to set attribute
        #   set_<attr>()
        # as attribute name in status instance:
        #   status.<attr>
        self._contr_set_fun = getattr(self._ecoal_contr, f"set_{state_attr}")

    def update(self) -> None:
        """Fetch new state data for the sensor.

        This is the only method that should fetch new data for Home Assistant.
        """
        status = self._ecoal_contr.get_cached_status()
        self._attr_is_on = getattr(status, self._state_attr)

    def invalidate_ecoal_cache(self):
        """Invalidate ecoal interface cache.

        Forces that next read from ecaol interface to not use cache.
        """
        self._ecoal_contr.status = None

    def turn_on(self, **kwargs: Any) -> None:
        """Turn the device on."""
        self._contr_set_fun(1)
        self.invalidate_ecoal_cache()

    def turn_off(self, **kwargs: Any) -> None:
        """Turn the device off."""
        self._contr_set_fun(0)
        self.invalidate_ecoal_cache()
