"""Support for Ankuoo RecSwitch MS6126 devices."""

import logging

from pyrecswitch import RSNetwork, RSNetworkError
import voluptuous as vol

from homeassistant.components.switch import PLATFORM_SCHEMA, SwitchEntity
from homeassistant.const import CONF_HOST, CONF_MAC, CONF_NAME
import homeassistant.helpers.config_validation as cv

_LOGGER = logging.getLogger(__name__)

DEFAULT_NAME = "RecSwitch {0}"

DATA_RSN = "RSN"

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {
        vol.Required(CONF_HOST): cv.string,
        vol.Required(CONF_MAC): vol.All(cv.string, vol.Upper),
        vol.Optional(CONF_NAME): cv.string,
    }
)


async def async_setup_platform(hass, config, async_add_entities, discovery_info=None):
    """Set up the device."""

    host = config[CONF_HOST]
    mac_address = config[CONF_MAC]
    device_name = config.get(CONF_NAME)

    if not hass.data.get(DATA_RSN):
        hass.data[DATA_RSN] = RSNetwork()
        job = hass.data[DATA_RSN].create_datagram_endpoint()
        hass.async_create_task(job)

    device = hass.data[DATA_RSN].register_device(mac_address, host)
    async_add_entities([RecSwitchSwitch(device, device_name, mac_address)])


class RecSwitchSwitch(SwitchEntity):
    """Representation of a recswitch device."""

    def __init__(self, device, device_name, mac_address):
        """Initialize a recswitch device."""
        self.gpio_state = False
        self.device = device
        self.device_name = device_name
        self.mac_address = mac_address
        if not self.device_name:
            self.device_name = DEFAULT_NAME.format(self.mac_address)

    @property
    def unique_id(self):
        """Return the switch unique ID."""
        return self.mac_address

    @property
    def name(self):
        """Return the switch name."""
        return self.device_name

    @property
    def is_on(self):
        """Return true if switch is on."""
        return self.gpio_state

    async def async_turn_on(self, **kwargs):
        """Turn on the switch."""
        await self.async_set_gpio_status(True)

    async def async_turn_off(self, **kwargs):
        """Turn off the switch."""
        await self.async_set_gpio_status(False)

    async def async_set_gpio_status(self, status):
        """Set the switch status."""

        try:
            ret = await self.device.set_gpio_status(status)
            self.gpio_state = ret.state
        except RSNetworkError as error:
            _LOGGER.error("Setting status to %s: %r", self.name, error)

    async def async_update(self):
        """Update the current switch status."""

        try:
            ret = await self.device.get_gpio_status()
            self.gpio_state = ret.state
        except RSNetworkError as error:
            _LOGGER.error("Reading status from %s: %r", self.name, error)
