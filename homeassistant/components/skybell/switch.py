"""Switch support for the Skybell HD Doorbell."""
from __future__ import annotations

from typing import NamedTuple

import voluptuous as vol

from homeassistant.components.switch import PLATFORM_SCHEMA, SwitchEntity
from homeassistant.const import CONF_ENTITY_NAMESPACE, CONF_MONITORED_CONDITIONS
import homeassistant.helpers.config_validation as cv

from . import DEFAULT_ENTITY_NAMESPACE, DOMAIN as SKYBELL_DOMAIN, SkybellDevice


class SkybellSwitchMetadata(NamedTuple):
    """Metadata for an individual Skybell switch."""

    name: str


SWITCH_TYPES = {
    "do_not_disturb": SkybellSwitchMetadata(
        "Do Not Disturb",
    ),
    "motion_sensor": SkybellSwitchMetadata(
        "Motion Sensor",
    ),
}

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {
        vol.Optional(
            CONF_ENTITY_NAMESPACE, default=DEFAULT_ENTITY_NAMESPACE
        ): cv.string,
        vol.Required(CONF_MONITORED_CONDITIONS, default=[]): vol.All(
            cv.ensure_list, [vol.In(SWITCH_TYPES)]
        ),
    }
)


def setup_platform(hass, config, add_entities, discovery_info=None):
    """Set up the platform for a Skybell device."""
    skybell = hass.data.get(SKYBELL_DOMAIN)

    sensors = []
    for switch_type in config.get(CONF_MONITORED_CONDITIONS):
        for device in skybell.get_devices():
            sensors.append(SkybellSwitch(device, switch_type))

    add_entities(sensors, True)


class SkybellSwitch(SkybellDevice, SwitchEntity):
    """A switch implementation for Skybell devices."""

    def __init__(self, device, switch_type):
        """Initialize a light for a Skybell device."""
        super().__init__(device)
        self._switch_type = switch_type
        metadata = SWITCH_TYPES[self._switch_type]
        self._attr_name = f"{self._device.name} {metadata.name}"

    def turn_on(self, **kwargs):
        """Turn on the switch."""
        setattr(self._device, self._switch_type, True)

    def turn_off(self, **kwargs):
        """Turn off the switch."""
        setattr(self._device, self._switch_type, False)

    @property
    def is_on(self):
        """Return true if device is on."""
        return getattr(self._device, self._switch_type)
