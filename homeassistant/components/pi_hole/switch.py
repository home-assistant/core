"""Support for getting statistical data from a Pi-hole system."""
import logging

from homeassistant.components.switch import SwitchEntity

from . import PiHoleDataUpdateCoordinator, PiHoleEntity
from .const import DOMAIN as PIHOLE_DOMAIN, STATUS_ENABLED

LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass, entry, async_add_entities):
    """Set up the pi-hole sensor."""
    coordinator = hass.data[PIHOLE_DOMAIN][entry.entry_id]
    server_unique_id = coordinator.unique_id
    switches = [PiHoleSwitch(coordinator, server_unique_id)]
    async_add_entities(switches, True)


class PiHoleSwitch(PiHoleEntity, SwitchEntity):
    """Switch that enables or disables a Pi-Hole."""

    def __init__(self, coordinator: PiHoleDataUpdateCoordinator, server_unique_id: str):
        """Initialize a Pi-hole switch."""
        super().__init__(
            coordinator=coordinator, name=coordinator.name, device_id=server_unique_id,
        )
        self._server_unique_id = server_unique_id
        self._duration = coordinator.disable_seconds
        self._force_update = False

    @property
    def icon(self):
        """Return switch icon."""
        return "mdi:shield-star"

    @property
    def unique_id(self):
        """Return the unique id of the sensor."""
        return f"{self._server_unique_id}"

    @property
    def is_on(self):
        """Return the state of the device."""
        if self.coordinator.data is not None:
            return self.coordinator.data.get("status") == STATUS_ENABLED

        return None

    async def async_turn_on(self, **kwargs):
        """Enable the Pi-Hole."""
        result = await self.coordinator.api.enable()
        LOGGER.debug("Enable Pi-Hole (%s) result: %s", self.name, result)
        await self.coordinator.async_request_refresh()

    async def async_turn_off(self, **kwargs):
        """Disable the Pi-Hole."""
        result = await self.coordinator.api.disable(self._duration)
        LOGGER.debug("Disable Pi-Hole (%s) result: %s", self.name, result)
        await self.coordinator.async_request_refresh()
