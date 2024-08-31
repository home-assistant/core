"""The Keenetic Client class."""

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import KeeneticRouter
from .const import DOMAIN, ROUTER


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up device tracker for Keenetic NDMS2 component."""
    router: KeeneticRouter = hass.data[DOMAIN][config_entry.entry_id][ROUTER]

    async_add_entities([RouterOnlineBinarySensor(router)])


class RouterOnlineBinarySensor(BinarySensorEntity):
    """Representation router connection status."""

    _attr_device_class = BinarySensorDeviceClass.CONNECTIVITY
    _attr_should_poll = False
    _attr_has_entity_name = True

    def __init__(self, router: KeeneticRouter) -> None:
        """Initialize the APCUPSd binary device."""
        self._router = router
        self._attr_unique_id = f"online_{router.config_entry.entry_id}"
        self._attr_device_info = router.device_info

    @property
    def is_on(self):
        """Return true if the UPS is online, else false."""
        return self._router.available

    async def async_added_to_hass(self) -> None:
        """Client entity created."""
        self.async_on_remove(
            async_dispatcher_connect(
                self.hass,
                self._router.signal_update,
                self.async_write_ha_state,
            )
        )
