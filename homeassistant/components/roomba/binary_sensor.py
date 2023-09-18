"""Roomba binary sensor entities."""
from homeassistant.components.binary_sensor import BinarySensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import roomba_reported_state
from .const import BLID, DOMAIN, ROOMBA_SESSION
from .irobot_base import IRobotEntity


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the iRobot Roomba vacuum cleaner."""
    domain_data = hass.data[DOMAIN][config_entry.entry_id]
    roomba = domain_data[ROOMBA_SESSION]
    blid = domain_data[BLID]
    status = roomba_reported_state(roomba).get("bin", {})
    if "full" in status:
        roomba_vac = RoombaBinStatus(roomba, blid)
        async_add_entities([roomba_vac], True)


class RoombaBinStatus(IRobotEntity, BinarySensorEntity):
    """Class to hold Roomba Sensor basic info."""

    _attr_icon = "mdi:delete-variant"
    _attr_translation_key = "bin_full"

    @property
    def unique_id(self):
        """Return the ID of this sensor."""
        return f"bin_{self._blid}"

    @property
    def is_on(self):
        """Return the state of the sensor."""
        return roomba_reported_state(self.vacuum).get("bin", {}).get("full", False)

    def new_state_filter(self, new_state):
        """Filter the new state."""
        return "bin" in new_state
