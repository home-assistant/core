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
        raise PlatformNotReady from exc

    switches = []
    async for outlet in outlets:
        switches.append(AtenSwitch(dev, mac, outlet.id, outlet.name))

    async_add_entities(switches, True)


class AtenSwitch(SwitchEntity):
    """Represents an ATEN PE switch."""

    _attr_device_class = DEVICE_CLASS_OUTLET

    def __init__(self, device, mac, outlet, name):
        """Initialize an ATEN PE switch."""
        self._device = device
        self._outlet = outlet
        self._attr_unique_id = f"{mac}-{outlet}"
        self._attr_name = name or f"Outlet {outlet}"

    async def async_turn_on(self, **kwargs):
        """Turn the switch on."""
        await self._device.setOutletStatus(self._outlet, "on")
        self._attr_is_on = True

    async def async_turn_off(self, **kwargs):
        """Turn the switch off."""
        await self._device.setOutletStatus(self._outlet, "off")
        self._attr_is_on = False

    async def async_update(self):
        """Process update from entity."""
        status = await self._device.displayOutletStatus(self._outlet)
        if status == "on":
            self._attr_is_on = True
            self._attr_current_power_w = await self._device.outletPower(self._outlet)
        else:
            self._attr_is_on = False
            self._attr_current_power_w = 0.0
