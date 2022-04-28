"""Support for XS1 switches."""
from __future__ import annotations

from xs1_api_client.api_constants import ActuatorType

from homeassistant.components.switch import SwitchEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType

from . import ACTUATORS, DOMAIN as COMPONENT_DOMAIN, XS1DeviceEntity


def setup_platform(
    hass: HomeAssistant,
    config: ConfigType,
    add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None,
) -> None:
    """Set up the XS1 switch platform."""
    actuators = hass.data[COMPONENT_DOMAIN][ACTUATORS]

    switch_entities = []
    for actuator in actuators:
        if (actuator.type() == ActuatorType.SWITCH) or (
            actuator.type() == ActuatorType.DIMMER
        ):
            switch_entities.append(XS1SwitchEntity(actuator))

    add_entities(switch_entities)


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

    def turn_on(self, **kwargs):
        """Turn the device on."""
        self.device.turn_on()

    def turn_off(self, **kwargs):
        """Turn the device off."""
        self.device.turn_off()
