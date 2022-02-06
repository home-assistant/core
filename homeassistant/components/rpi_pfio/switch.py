"""Support for switches using the PiFace Digital I/O module on a RPi."""
from __future__ import annotations

import voluptuous as vol

from homeassistant.components import rpi_pfio
from homeassistant.components.switch import PLATFORM_SCHEMA, SwitchEntity
from homeassistant.const import ATTR_NAME, DEVICE_DEFAULT_NAME
from homeassistant.core import HomeAssistant
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType

ATTR_INVERT_LOGIC = "invert_logic"

CONF_PORTS = "ports"

DEFAULT_INVERT_LOGIC = False

PORT_SCHEMA = vol.Schema(
    {
        vol.Optional(ATTR_NAME): cv.string,
        vol.Optional(ATTR_INVERT_LOGIC, default=DEFAULT_INVERT_LOGIC): cv.boolean,
    }
)

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {vol.Optional(CONF_PORTS, default={}): vol.Schema({cv.positive_int: PORT_SCHEMA})}
)


def setup_platform(
    hass: HomeAssistant,
    config: ConfigType,
    add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None,
) -> None:
    """Set up the PiFace Digital Output devices."""
    switches = []
    ports = config[CONF_PORTS]
    for port, port_entity in ports.items():
        name = port_entity.get(ATTR_NAME)
        invert_logic = port_entity[ATTR_INVERT_LOGIC]

        switches.append(RPiPFIOSwitch(port, name, invert_logic))
    add_entities(switches)


class RPiPFIOSwitch(SwitchEntity):
    """Representation of a PiFace Digital Output."""

    def __init__(self, port, name, invert_logic):
        """Initialize the pin."""
        self._port = port
        self._name = name or DEVICE_DEFAULT_NAME
        self._invert_logic = invert_logic
        self._state = False
        rpi_pfio.write_output(self._port, 1 if self._invert_logic else 0)

    @property
    def name(self):
        """Return the name of the switch."""
        return self._name

    @property
    def should_poll(self):
        """Return the polling state."""
        return False

    @property
    def is_on(self):
        """Return true if device is on."""
        return self._state

    def turn_on(self, **kwargs):
        """Turn the device on."""
        rpi_pfio.write_output(self._port, 0 if self._invert_logic else 1)
        self._state = True
        self.schedule_update_ha_state()

    def turn_off(self, **kwargs):
        """Turn the device off."""
        rpi_pfio.write_output(self._port, 1 if self._invert_logic else 0)
        self._state = False
        self.schedule_update_ha_state()
