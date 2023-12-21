"""Support for VELUX sensors."""
from pyvlx import PyVLX

from homeassistant.components.sensor import SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up sensor(s) for Velux platform."""
    entities = []
    pyvlx: PyVLX = hass.data[DOMAIN][entry.entry_id]
    entities.append(VeluxConnectionCounter(pyvlx))
    async_add_entities(entities)


class VeluxConnectionCounter(SensorEntity):
    """Representation of a Velux number."""

    def __init__(self, pyvlx: PyVLX) -> None:
        """Initialize the cover."""
        self.pyvlx: PyVLX = pyvlx

    @property
    def name(self) -> str:
        """Name of the entity."""
        return "KLF200 Connection Counter"

    @property
    def device_info(self) -> DeviceInfo:
        """Return specific device attributes."""
        return {
            "identifiers": {(DOMAIN, self.unique_id)},
            "connections": {("Host", self.pyvlx.config.host)},  # type: ignore[arg-type]
            "name": "KLF200 Gateway",
            "manufacturer": "Velux",
            "sw_version": self.pyvlx.version,
        }

    @property
    def unique_id(self) -> str:
        """Return the unique ID of this cover."""
        return "KLF200ConnectionCounter"

    @property
    def native_value(self) -> int:
        """Return the value reported by the sensor."""
        return self.pyvlx.connection.connection_counter
