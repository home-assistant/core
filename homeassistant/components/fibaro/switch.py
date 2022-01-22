"""Support for Fibaro switches."""
from __future__ import annotations

from typing import Any

from homeassistant.components.switch import (
    DOMAIN,
    SwitchEntity,
    SwitchEntityDescription,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType
from homeassistant.util import convert

from . import FIBARO_DEVICES, FibaroDevice


def setup_platform(
    hass: HomeAssistant,
    config: ConfigType,
    add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None,
) -> None:
    """Set up the Fibaro switches."""
    if discovery_info is None:
        return

    entities: list[FibaroSwitch] = []
    for fibaro_device in hass.data[FIBARO_DEVICES]["switch"]:
        entity_description = SwitchEntityDescription(
            key="switch", name=fibaro_device.friendly_name
        )
        entities.append(FibaroSwitch(fibaro_device, entity_description))

    add_entities(entities, True)


class FibaroSwitch(FibaroDevice, SwitchEntity):
    """Representation of a Fibaro Switch."""

    def __init__(self, fibaro_device: Any, entity_description: SwitchEntityDescription):
        """Initialize the Fibaro device."""
        super().__init__(fibaro_device)
        self.entity_description = entity_description
        self.entity_id = f"{DOMAIN}.{self.ha_id}"

    def turn_on(self, **kwargs: Any) -> None:
        """Turn device on."""
        self.call_turn_on()
        self._attr_is_on = True

    def turn_off(self, **kwargs: Any) -> None:
        """Turn device off."""
        self.call_turn_off()
        self._attr_is_on = False

    @property
    def current_power_w(self) -> float | None:
        """Return the current power usage in W."""
        if "power" in self.fibaro_device.interfaces:
            return convert(self.fibaro_device.properties.power, float)
        return None

    @property
    def today_energy_kwh(self) -> float | None:
        """Return the today total energy usage in kWh."""
        if "energy" in self.fibaro_device.interfaces:
            return convert(self.fibaro_device.properties.energy, float)
        return None

    def update(self) -> None:
        """Update device state."""
        self._attr_is_on = self.current_binary_state
