"""The ATEN PE switch component."""

import logging

from atenpdu import AtenPE
import voluptuous as vol

from homeassistant.components.snmp.const import (
    CONF_AUTH_KEY,
    CONF_COMMUNITY,
    CONF_PRIV_KEY,
    DEFAULT_PORT,
)
from homeassistant.components.switch import (
    DEVICE_CLASS_OUTLET,
    PLATFORM_SCHEMA,
    SwitchDevice,
)
from homeassistant.const import CONF_HOST, CONF_PORT, CONF_USERNAME
import homeassistant.helpers.config_validation as cv

_LOGGER = logging.getLogger(__name__)

DEFAULT_COMMUNITY = "private"
DEFAULT_USERNAME = "administrator"

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {
        vol.Required(CONF_HOST): cv.string,
        vol.Optional(CONF_PORT, default=DEFAULT_PORT): cv.port,
        vol.Optional(CONF_COMMUNITY, default=DEFAULT_COMMUNITY): cv.string,
        vol.Optional(CONF_USERNAME, default=DEFAULT_USERNAME): cv.string,
        vol.Optional(CONF_AUTH_KEY): cv.string,
        vol.Optional(CONF_PRIV_KEY): cv.string,
    }
)


async def async_setup_platform(hass, config, async_add_entities, discovery_info=None):
    """Set up the ATEN PE switch."""
    dev = AtenPE(
        node=config[CONF_HOST],
        serv=config.get(CONF_PORT),
        community=config.get(CONF_COMMUNITY),
        username=config.get(CONF_USERNAME),
        authkey=config.get(CONF_AUTH_KEY),
        privkey=config.get(CONF_PRIV_KEY),
    )

    switches = []
    for outlet in dev.outlets:
        if outlet.name:
            switches.append(AtenSwitch(dev, outlet.id, outlet.name))

    async_add_entities(switches)
    return True


class AtenSwitch(SwitchDevice):
    """Represents an ATEN PE switch."""

    def __init__(self, device, outlet, name):
        """Initialize an ATEN PE switch."""
        self._device = device
        self._outlet = outlet
        self._name = name
        self._enabled = False
        self._outlet_power = 0.0

    @property
    def unique_id(self) -> str:
        """Return a unique ID."""
        return f"{self._device.deviceMAC}-{self._outlet}"

    @property
    def name(self) -> str:
        """Return the name of the entity."""
        return self._name

    @property
    def device_class(self) -> str:
        """Return the class of this device, from component DEVICE_CLASSES."""
        return DEVICE_CLASS_OUTLET

    @property
    def is_on(self) -> bool:
        """Return True if entity is on."""
        return self._enabled

    @property
    def current_power_w(self) -> float:
        """Return the current power usage in W."""
        return self._outlet_power

    def turn_on(self, **kwargs):
        """Turn the switch on."""
        self._device.setOutletStatus(self._outlet, "on")
        self._enabled = True

    def turn_off(self, **kwargs):
        """Turn the switch off."""
        self._device.setOutletStatus(self._outlet, "off")
        self._enabled = False

    def update(self):
        """Process update from entity."""
        status = self._device.displayOutletStatus(self._outlet)
        if status == "on":
            self._enabled = True
            self._outlet_power = self._device.outletPower(self._outlet)
        elif status == "off":
            self._enabled = False
            self._outlet_power = 0.0
