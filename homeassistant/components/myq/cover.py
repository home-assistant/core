"""Support for MyQ-Enabled Garage Doors."""
import logging

import voluptuous as vol

from homeassistant.components.cover import (
    PLATFORM_SCHEMA,
    SUPPORT_CLOSE,
    SUPPORT_OPEN,
    CoverDevice,
)
from homeassistant.config_entries import SOURCE_IMPORT
from homeassistant.const import (
    CONF_PASSWORD,
    CONF_TYPE,
    CONF_USERNAME,
    STATE_CLOSED,
    STATE_CLOSING,
    STATE_OPENING,
)
from homeassistant.helpers import config_validation as cv

from .const import DOMAIN, MYQ_DEVICE_STATE, MYQ_DEVICE_STATE_ONLINE, MYQ_TO_HASS

_LOGGER = logging.getLogger(__name__)


PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {
        vol.Required(CONF_USERNAME): cv.string,
        vol.Required(CONF_PASSWORD): cv.string,
        # This parameter is no longer used; keeping it to avoid a breaking change in
        # a hotfix, but in a future main release, this should be removed:
        vol.Optional(CONF_TYPE): cv.string,
    },
)


async def async_setup_platform(hass, config, async_add_entities, discovery_info=None):
    """Set up the platform."""

    hass.async_create_task(
        hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": SOURCE_IMPORT},
            data={
                CONF_USERNAME: config[CONF_USERNAME],
                CONF_PASSWORD: config[CONF_PASSWORD],
            },
        )
    )


async def async_setup_entry(hass, config_entry, async_add_entities):
    """Set up mysq covers."""
    myq = hass.data[DOMAIN][config_entry.entry_id]
    async_add_entities([MyQDevice(device) for device in myq.covers.values()], True)


class MyQDevice(CoverDevice):
    """Representation of a MyQ cover."""

    def __init__(self, device):
        """Initialize with API object, device id."""
        self._device = device

    @property
    def device_class(self):
        """Define this cover as a garage door."""
        return "garage"

    @property
    def name(self):
        """Return the name of the garage door if any."""
        return self._device.name

    @property
    def available(self):
        """Return if the device is online."""
        # Not all devices report online so assume True if its missing
        return self._device.device_json[MYQ_DEVICE_STATE].get(
            MYQ_DEVICE_STATE_ONLINE, True
        )

    @property
    def is_closed(self):
        """Return true if cover is closed, else False."""
        return MYQ_TO_HASS.get(self._device.state) == STATE_CLOSED

    @property
    def is_closing(self):
        """Return if the cover is closing or not."""
        return MYQ_TO_HASS.get(self._device.state) == STATE_CLOSING

    @property
    def is_opening(self):
        """Return if the cover is opening or not."""
        return MYQ_TO_HASS.get(self._device.state) == STATE_OPENING

    @property
    def supported_features(self):
        """Flag supported features."""
        return SUPPORT_OPEN | SUPPORT_CLOSE

    @property
    def unique_id(self):
        """Return a unique, Home Assistant friendly identifier for this entity."""
        return self._device.device_id

    async def async_close_cover(self, **kwargs):
        """Issue close command to cover."""
        await self._device.close()
        # Writes closing state
        self.async_write_ha_state()

    async def async_open_cover(self, **kwargs):
        """Issue open command to cover."""
        await self._device.open()
        # Writes opening state
        self.async_write_ha_state()

    async def async_update(self):
        """Update status of cover."""
        await self._device.update()

    @property
    def device_info(self):
        """Return the device_info of the device."""
        device_info = {
            "identifiers": {(DOMAIN, self._device.device_id)},
            "name": self._device.name,
            "manufacturer": "The Chamberlain Group Inc.",
            "sw_version": self._device.firmware_version,
        }
        if self._device.parent_device_id:
            device_info["via_device"] = (DOMAIN, self._device.parent_device_id)
        return device_info
