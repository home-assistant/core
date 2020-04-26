"""Support for Gogogate2 garage Doors."""
import logging
from typing import Callable, List, Optional

from homeassistant.components.cover import SUPPORT_CLOSE, SUPPORT_OPEN, CoverDevice
from homeassistant.config_entries import SOURCE_IMPORT, ConfigEntry
from homeassistant.const import CONF_NAME, STATE_CLOSED
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import Entity

from .common import get_api
from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

DEFAULT_NAME = "gogogate2"


async def async_setup_platform(
    hass: HomeAssistant, config: dict, add_entities: Callable, discovery_info=None
) -> None:
    """Convert old style file configs to new style configs."""
    await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_IMPORT}, data=config
    )


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: Callable[[List[Entity], Optional[bool]], None],
) -> None:
    """Set up the config entry."""
    mygogogate2 = get_api(config_entry.data)
    devices = await hass.async_add_executor_job(mygogogate2.get_devices)

    async_add_entities(
        [
            MyGogogate2Device(mygogogate2, door, config_entry.data[CONF_NAME])
            for door in devices
        ]
    )


class MyGogogate2Device(CoverDevice):
    """Representation of a Gogogate2 cover."""

    def __init__(self, mygogogate2, device, name):
        """Initialize with API object, device id."""
        self.mygogogate2 = mygogogate2
        self.device_id = device["door"]
        self._name = name or device["name"]
        self._status = device["status"]
        self._available = None

    @property
    def name(self):
        """Return the name of the garage door if any."""
        return self._name if self._name else DEFAULT_NAME

    @property
    def is_closed(self):
        """Return true if cover is closed, else False."""
        return self._status == STATE_CLOSED

    @property
    def device_class(self):
        """Return the class of this device, from component DEVICE_CLASSES."""
        return "garage"

    @property
    def supported_features(self):
        """Flag supported features."""
        return SUPPORT_OPEN | SUPPORT_CLOSE

    @property
    def available(self):
        """Could the device be accessed during the last update call."""
        return self._available

    def close_cover(self, **kwargs):
        """Issue close command to cover."""
        self.mygogogate2.close_device(self.device_id)

    def open_cover(self, **kwargs):
        """Issue open command to cover."""
        self.mygogogate2.open_device(self.device_id)

    def update(self):
        """Update status of cover."""
        _LOGGER.error("UPDATING!!!!")
        try:
            self._status = self.mygogogate2.get_status(self.device_id)
            self._available = True
        except Exception as ex:  # pylint: disable=broad-except
            _LOGGER.error("%s", ex)
            self._status = None
            self._available = False
