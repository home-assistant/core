"""Support for Aurora Forecast binary sensor."""
from homeassistant.components.binary_sensor import BinarySensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import COORDINATOR, DOMAIN
from .entity import AuroraEntity


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entries: AddEntitiesCallback
) -> None:
    """Set up the binary_sensor platform."""
    coordinator = hass.data[DOMAIN][entry.entry_id][COORDINATOR]
    name = f"{coordinator.name} Aurora Visibility Alert"

    entity = AuroraSensor(coordinator=coordinator, name=name, icon="mdi:hazard-lights")

    async_add_entries([entity])


class AuroraSensor(AuroraEntity, BinarySensorEntity):
    """Implementation of an aurora sensor."""

    @property
    def is_on(self):
        """Return true if aurora is visible."""
        return self.coordinator.data > self.coordinator.threshold
