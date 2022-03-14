"""Switch support for the Skybell HD Doorbell."""
from __future__ import annotations

import voluptuous as vol

from homeassistant.components.switch import (
    PLATFORM_SCHEMA,
    SwitchEntity,
    SwitchEntityDescription,
)
from homeassistant.const import CONF_ENTITY_NAMESPACE, CONF_MONITORED_CONDITIONS
from homeassistant.core import HomeAssistant
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType

from . import DEFAULT_ENTITY_NAMESPACE, DOMAIN as SKYBELL_DOMAIN, SkybellDevice

SWITCH_TYPES: tuple[SwitchEntityDescription, ...] = (
    SwitchEntityDescription(
        key="do_not_disturb",
        name="Do Not Disturb",
    ),
    SwitchEntityDescription(
        key="motion_sensor",
        name="Motion Sensor",
    ),
)
MONITORED_CONDITIONS: list[str] = [desc.key for desc in SWITCH_TYPES]


PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {
        vol.Optional(
            CONF_ENTITY_NAMESPACE, default=DEFAULT_ENTITY_NAMESPACE
        ): cv.string,
        vol.Required(CONF_MONITORED_CONDITIONS, default=[]): vol.All(
            cv.ensure_list, [vol.In(MONITORED_CONDITIONS)]
        ),
    }
)


def setup_platform(
    hass: HomeAssistant,
    config: ConfigType,
    add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None,
) -> None:
    """Set up the platform for a Skybell device."""
    skybell = hass.data[SKYBELL_DOMAIN]

    switches = [
        SkybellSwitch(device, description)
        for device in skybell.get_devices()
        for description in SWITCH_TYPES
        if description.key in config[CONF_MONITORED_CONDITIONS]
    ]

    add_entities(switches, True)


class SkybellSwitch(SkybellDevice, SwitchEntity):
    """A switch implementation for Skybell devices."""

    def __init__(
        self,
        device,
        description: SwitchEntityDescription,
    ):
        """Initialize a light for a Skybell device."""
        super().__init__(device)
        self.entity_description = description
        self._attr_name = f"{self._device.name} {description.name}"

    def turn_on(self, **kwargs):
        """Turn on the switch."""
        setattr(self._device, self.entity_description.key, True)

    def turn_off(self, **kwargs):
        """Turn off the switch."""
        setattr(self._device, self.entity_description.key, False)

    @property
    def is_on(self):
        """Return true if device is on."""
        return getattr(self._device, self.entity_description.key)
