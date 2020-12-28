"""Support for Soma Smartshades."""
import logging

from api.soma_api import SomaApi
from requests import RequestException
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, CONF_PORT
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.typing import HomeAssistantType

from .const import API, DOMAIN, HOST, PORT

DEVICES = "devices"

_LOGGER = logging.getLogger(__name__)

CONFIG_SCHEMA = vol.Schema(
    {
        DOMAIN: vol.Schema(
            {vol.Required(CONF_HOST): cv.string, vol.Required(CONF_PORT): cv.string}
        )
    },
    extra=vol.ALLOW_EXTRA,
)

SOMA_COMPONENTS = ["cover", "sensor"]


async def async_setup(hass, config):
    """Set up the Soma component."""
    if DOMAIN not in config:
        return True

    hass.async_create_task(
        hass.config_entries.flow.async_init(
            DOMAIN,
            data=config[DOMAIN],
            context={"source": config_entries.SOURCE_IMPORT},
        )
    )

    return True


async def async_setup_entry(hass: HomeAssistantType, entry: ConfigEntry):
    """Set up Soma from a config entry."""
    hass.data[DOMAIN] = {}
    hass.data[DOMAIN][API] = SomaApi(entry.data[HOST], entry.data[PORT])
    devices = await hass.async_add_executor_job(hass.data[DOMAIN][API].list_devices)
    hass.data[DOMAIN][DEVICES] = devices["shades"]

    for component in SOMA_COMPONENTS:
        hass.async_create_task(
            hass.config_entries.async_forward_entry_setup(entry, component)
        )

    return True


async def async_unload_entry(hass: HomeAssistantType, entry: ConfigEntry):
    """Unload a config entry."""
    return True


class SomaEntity(Entity):
    """Representation of a generic Soma device."""

    def __init__(self, device, api):
        """Initialize the Soma device."""
        self.device = device
        self.api = api
        self.current_position = 50
        self.battery_state = 0
        self.is_available = True

    @property
    def available(self):
        """Return true if the last API commands returned successfully."""
        return self.is_available

    @property
    def unique_id(self):
        """Return the unique id base on the id returned by pysoma API."""
        return self.device["mac"]

    @property
    def name(self):
        """Return the name of the device."""
        return self.device["name"]

    @property
    def device_info(self):
        """Return device specific attributes.

        Implemented by platform classes.
        """
        return {
            "identifiers": {(DOMAIN, self.unique_id)},
            "name": self.name,
            "manufacturer": "Wazombi Labs",
        }

    async def async_update(self):
        """Update the device with the latest data."""
        try:
            response = await self.hass.async_add_executor_job(
                self.api.get_shade_state, self.device["mac"]
            )
        except RequestException:
            _LOGGER.error("Connection to SOMA Connect failed")
            self.is_available = False
            return
        if response["result"] != "success":
            _LOGGER.error(
                "Unable to reach device %s (%s)", self.device["name"], response["msg"]
            )
            self.is_available = False
            return
        self.current_position = 100 - response["position"]
        try:
            response = await self.hass.async_add_executor_job(
                self.api.get_battery_level, self.device["mac"]
            )
        except RequestException:
            _LOGGER.error("Connection to SOMA Connect failed")
            self.is_available = False
            return
        if response["result"] != "success":
            _LOGGER.error(
                "Unable to reach device %s (%s)", self.device["name"], response["msg"]
            )
            self.is_available = False
            return
        # https://support.somasmarthome.com/hc/en-us/articles/360026064234-HTTP-API
        # battery_level response is expected to be min = 360, max 410 for
        # 0-100% levels above 410 are consider 100% and below 360, 0% as the
        # device considers 360 the minimum to move the motor.
        _battery = round(2 * (response["battery_level"] - 360))
        battery = max(min(100, _battery), 0)
        self.battery_state = battery
        self.is_available = True
