"""Support for Switchmate."""
from datetime import timedelta

# pylint: disable=import-error
import switchmate
import voluptuous as vol

from homeassistant.components.switch import PLATFORM_SCHEMA, SwitchEntity
from homeassistant.const import CONF_MAC, CONF_NAME
import homeassistant.helpers.config_validation as cv

CONF_FLIP_ON_OFF = "flip_on_off"
DEFAULT_NAME = "Switchmate"

SCAN_INTERVAL = timedelta(minutes=30)

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {
        vol.Required(CONF_MAC): cv.string,
        vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
        vol.Optional(CONF_FLIP_ON_OFF, default=False): cv.boolean,
    }
)


def setup_platform(hass, config, add_entities, discovery_info=None) -> None:
    """Perform the setup for Switchmate devices."""
    name = config.get(CONF_NAME)
    mac_addr = config[CONF_MAC]
    flip_on_off = config[CONF_FLIP_ON_OFF]
    add_entities([SwitchmateEntity(mac_addr, name, flip_on_off)], True)


class SwitchmateEntity(SwitchEntity):
    """Representation of a Switchmate."""

    def __init__(self, mac, name, flip_on_off) -> None:
        """Initialize the Switchmate."""

        self._mac = mac
        self._name = name
        self._device = switchmate.Switchmate(mac=mac, flip_on_off=flip_on_off)

    @property
    def unique_id(self) -> str:
        """Return a unique, Home Assistant friendly identifier for this entity."""
        return self._mac.replace(":", "")

    @property
    def available(self) -> bool:
        """Return True if entity is available."""
        return self._device.available

    @property
    def name(self) -> str:
        """Return the name of the switch."""
        return self._name

    def update(self) -> None:
        """Synchronize state with switch."""
        self._device.update()

    @property
    def is_on(self) -> bool:
        """Return true if it is on."""
        return self._device.state

    def turn_on(self, **kwargs) -> None:
        """Turn the switch on."""
        self._device.turn_on()

    def turn_off(self, **kwargs) -> None:
        """Turn the switch off."""
        self._device.turn_off()
