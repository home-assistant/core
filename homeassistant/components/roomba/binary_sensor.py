"""Roomba binary sensor entities."""

from propcache.api import cached_property

from homeassistant.components.binary_sensor import BinarySensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import roomba_reported_state
from .const import DOMAIN
from .entity import IRobotEntity
from .models import RoombaData


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the iRobot Roomba vacuum cleaner."""
    domain_data: RoombaData = hass.data[DOMAIN][config_entry.entry_id]
    roomba = domain_data.roomba
    blid = domain_data.blid
    status = roomba_reported_state(roomba).get("bin", {})
    if "full" in status:
        roomba_vac = RoombaBinStatus(roomba, blid)
        async_add_entities([roomba_vac])


class RoombaBinStatus(IRobotEntity, BinarySensorEntity):
    """Class to hold Roomba Sensor basic info."""

    _attr_translation_key = "bin_full"

    @cached_property
    def unique_id(self) -> str:
        """Return the ID of this sensor."""
        return f"bin_{self._blid}"

    @cached_property
    def is_on(self) -> bool:
        """Return the state of the sensor."""
        return roomba_reported_state(self.vacuum).get("bin", {}).get("full", False)

    def new_state_filter(self, new_state):
        """Filter the new state."""
        return "bin" in new_state
