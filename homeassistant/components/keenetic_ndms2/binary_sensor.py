"""The Keenetic Client class."""
import logging

from homeassistant.components.binary_sensor import (
    DEVICE_CLASS_CONNECTIVITY,
    BinarySensorEntity,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.dispatcher import async_dispatcher_connect

from . import KeeneticRouter
from .const import DOMAIN, ROUTER

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant, config_entry: ConfigEntry, async_add_entities
):
    """Set up device tracker for Keenetic NDMS2 component."""
    router: KeeneticRouter = hass.data[DOMAIN][config_entry.entry_id][ROUTER]

    async_add_entities([RouterOnlineBinarySensor(router)])


class RouterOnlineBinarySensor(BinarySensorEntity):
    """Representation router connection status."""

    _attr_device_class = DEVICE_CLASS_CONNECTIVITY
    _attr_should_poll = False

    def __init__(self, router: KeeneticRouter) -> None:
        """Initialize the APCUPSd binary device."""
        self._router = router

    @property
    def name(self):
        """Return the name of the online status sensor."""
        return f"{self._router.name} Online"

    @property
    def unique_id(self) -> str:
        """Return a unique identifier for this device."""
        return f"online_{self._router.config_entry.entry_id}"

    @property
    def is_on(self):
        """Return true if the UPS is online, else false."""
        return self._router.available

    @property
    def device_info(self):
        """Return a client description for device registry."""
        return self._router.device_info

    async def async_added_to_hass(self):
        """Client entity created."""
        self.async_on_remove(
            async_dispatcher_connect(
                self.hass,
                self._router.signal_update,
                self.async_write_ha_state,
            )
        )
