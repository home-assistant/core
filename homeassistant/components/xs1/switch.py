"""Support for XS1 switches."""

from __future__ import annotations

from typing import Any

from xs1_api_client.api_constants import ActuatorType

from homeassistant.components.switch import SwitchEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType

from . import ACTUATORS, DOMAIN
from .entity import XS1DeviceEntity


def setup_platform(
    hass: HomeAssistant,
    config: ConfigType,
    add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None,
) -> None:
    """Set up the XS1 switch platform."""
    actuators = hass.data[DOMAIN][ACTUATORS]

    add_entities(
        XS1SwitchEntity(actuator)
        for actuator in actuators
        if (actuator.type() == ActuatorType.SWITCH)
        or (actuator.type() == ActuatorType.DIMMER)
    )


class XS1SwitchEntity(XS1DeviceEntity, SwitchEntity):
    """Representation of a XS1 switch actuator."""

    @property
    def name(self):
        """Return the name of the device if any."""
        return self.device.name()

    @property
    def is_on(self):
        """Return true if switch is on."""
        return self.device.value() == 100

    def turn_on(self, **kwargs: Any) -> None:
        """Turn the device on."""
        self.device.turn_on()

    def turn_off(self, **kwargs: Any) -> None:
        """Turn the device off."""
        self.device.turn_off()
