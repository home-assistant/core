"""Support for Aurora Forecast sensor."""
from __future__ import annotations

from homeassistant.components.sensor import SensorEntity, SensorStateClass
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import PERCENTAGE
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import COORDINATOR, DOMAIN
from .entity import AuroraEntity


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entries: AddEntitiesCallback
) -> None:
    """Set up the sensor platform."""
    coordinator = hass.data[DOMAIN][entry.entry_id][COORDINATOR]

    entity = AuroraSensor(
        coordinator=coordinator,
        translation_key="visibility",
    )

    async_add_entries([entity])


class AuroraSensor(AuroraEntity, SensorEntity):
    """Implementation of an aurora sensor."""

    _attr_native_unit_of_measurement = PERCENTAGE
    _attr_state_class = SensorStateClass.MEASUREMENT

    @property
    def native_value(self) -> int:
        """Return % chance the aurora is visible."""
        return self.coordinator.data
