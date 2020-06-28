"""The ATEN PE switch component."""

import logging

from atenpdu import AtenPE, AtenPEError
import voluptuous as vol

from homeassistant.components.switch import (
    DEVICE_CLASS_OUTLET,
    PLATFORM_SCHEMA,
    SwitchEntity,
)
from homeassistant.const import CONF_HOST, CONF_PORT, CONF_USERNAME
from homeassistant.exceptions import PlatformNotReady
import homeassistant.helpers.config_validation as cv

_LOGGER = logging.getLogger(__name__)

CONF_AUTH_KEY = "auth_key"
CONF_COMMUNITY = "community"
CONF_PRIV_KEY = "priv_key"
DEFAULT_COMMUNITY = "private"
DEFAULT_PORT = "161"
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
    node = config[CONF_HOST]
    serv = config[CONF_PORT]

    dev = AtenPE(
        node=node,
        serv=serv,
        community=config[CONF_COMMUNITY],
        username=config[CONF_USERNAME],
        authkey=config.get(CONF_AUTH_KEY),
        privkey=config.get(CONF_PRIV_KEY),
    )

    try:
        await hass.async_add_executor_job(dev.initialize)
        mac = await dev.deviceMAC()
        outlets = dev.outlets()
    except AtenPEError as exc:
        _LOGGER.error("Failed to initialize %s:%s: %s", node, serv, str(exc))
        raise PlatformNotReady

    switches = []
    async for outlet in outlets:
        switches.append(AtenSwitch(dev, mac, outlet.id, outlet.name))

    async_add_entities(switches)


class AtenSwitch(SwitchEntity):
    """Represents an ATEN PE switch."""

    def __init__(self, device, mac, outlet, name):
        """Initialize an ATEN PE switch."""
        self._device = device
        self._mac = mac
        self._outlet = outlet
        self._name = name or f"Outlet {outlet}"
        self._enabled = False
        self._outlet_power = 0.0

    @property
    def unique_id(self) -> str:
        """Return a unique ID."""
        return f"{self._mac}-{self._outlet}"

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

    async def async_turn_on(self, **kwargs):
        """Turn the switch on."""
        await self._device.setOutletStatus(self._outlet, "on")
        self._enabled = True

    async def async_turn_off(self, **kwargs):
        """Turn the switch off."""
        await self._device.setOutletStatus(self._outlet, "off")
        self._enabled = False

    async def async_update(self):
        """Process update from entity."""
        status = await self._device.displayOutletStatus(self._outlet)
        if status == "on":
            self._enabled = True
            self._outlet_power = await self._device.outletPower(self._outlet)
        elif status == "off":
            self._enabled = False
            self._outlet_power = 0.0
