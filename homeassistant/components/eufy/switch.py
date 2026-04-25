"""Support for EufyHome switches."""

from __future__ import annotations

from typing import Any

import lakeside

from homeassistant.components.switch import SwitchEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType


def setup_platform(
    hass: HomeAssistant,
    config: ConfigType,
    add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None,
) -> None:
    """Set up EufyHome switches."""
    if discovery_info is None:
        return
    add_entities([EufyHomeSwitch(discovery_info)], True)


class EufyHomeSwitch(SwitchEntity):
    """Representation of a EufyHome switch."""

    def __init__(self, device):
        """Initialize the light."""

        self._attr_name = device["name"]
        self._attr_unique_id = device["address"]
        self._switch = lakeside.switch(
            device["address"], device["code"], device["type"]
        )
        self._switch.connect()

    def update(self) -> None:
        """Synchronise state from the switch."""
        self._switch.update()
        self._attr_is_on = self._switch.power

    def turn_on(self, **kwargs: Any) -> None:
        """Turn the specified switch on."""
        try:
            self._switch.set_state(True)
        except BrokenPipeError:
            self._switch.connect()
            self._switch.set_state(power=True)

    def turn_off(self, **kwargs: Any) -> None:
        """Turn the specified switch off."""
        try:
            self._switch.set_state(False)
        except BrokenPipeError:
            self._switch.connect()
            self._switch.set_state(False)
