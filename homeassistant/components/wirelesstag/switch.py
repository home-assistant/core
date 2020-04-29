"""Switch implementation for Wireless Sensor Tags (wirelesstag.net)."""
import logging

import voluptuous as vol

from homeassistant.components.switch import PLATFORM_SCHEMA, SwitchDevice
from homeassistant.const import CONF_MONITORED_CONDITIONS
import homeassistant.helpers.config_validation as cv

from . import DOMAIN as WIRELESSTAG_DOMAIN, WirelessTagBaseSensor

_LOGGER = logging.getLogger(__name__)

ARM_TEMPERATURE = "temperature"
ARM_HUMIDITY = "humidity"
ARM_MOTION = "motion"
ARM_LIGHT = "light"
ARM_MOISTURE = "moisture"

# Switch types: Name, tag sensor type
SWITCH_TYPES = {
    ARM_TEMPERATURE: ["Arm Temperature", "temperature"],
    ARM_HUMIDITY: ["Arm Humidity", "humidity"],
    ARM_MOTION: ["Arm Motion", "motion"],
    ARM_LIGHT: ["Arm Light", "light"],
    ARM_MOISTURE: ["Arm Moisture", "moisture"],
}

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {
        vol.Required(CONF_MONITORED_CONDITIONS, default=[]): vol.All(
            cv.ensure_list, [vol.In(SWITCH_TYPES)]
        )
    }
)


def setup_platform(hass, config, add_entities, discovery_info=None):
    """Set up switches for a Wireless Sensor Tags."""
    platform = hass.data.get(WIRELESSTAG_DOMAIN)

    switches = []
    tags = platform.load_tags()
    for switch_type in config.get(CONF_MONITORED_CONDITIONS):
        for _, tag in tags.items():
            if switch_type in tag.allowed_monitoring_types:
                switches.append(WirelessTagSwitch(platform, tag, switch_type))

    add_entities(switches, True)


class WirelessTagSwitch(WirelessTagBaseSensor, SwitchDevice):
    """A switch implementation for Wireless Sensor Tags."""

    def __init__(self, api, tag, switch_type):
        """Initialize a switch for Wireless Sensor Tag."""
        super().__init__(api, tag)
        self._switch_type = switch_type
        self.sensor_type = SWITCH_TYPES[self._switch_type][1]
        self._name = f"{self._tag.name} {SWITCH_TYPES[self._switch_type][0]}"

    def turn_on(self, **kwargs):
        """Turn on the switch."""
        self._api.arm(self)

    def turn_off(self, **kwargs):
        """Turn on the switch."""
        self._api.disarm(self)

    @property
    def is_on(self) -> bool:
        """Return True if entity is on."""
        return self._state

    def updated_state_value(self):
        """Provide formatted value."""
        return self.principal_value

    @property
    def principal_value(self):
        """Provide actual value of switch."""
        attr_name = f"is_{self.sensor_type}_sensor_armed"
        return getattr(self._tag, attr_name, False)
