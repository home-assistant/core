"""Asus Router sensor module."""

from __future__ import annotations

from homeassistant.components.sensor import SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from .const import STATIC_SENSORS as SENSORS
from .dataclass import ARSensorDescription
from .entity import AREntity, async_setup_ar_entry
from .router import ARDevice


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Asus Router sensors."""

    await async_setup_ar_entry(
        hass,
        entry,
        async_add_entities,
        SENSORS,
        ARSensor,
    )


class ARSensor(AREntity, SensorEntity):
    """Asus Router sensor."""

    def __init__(
        self,
        coordinator: DataUpdateCoordinator,
        router: ARDevice,
        description: ARSensorDescription,
    ) -> None:
        """Initialize Asus Router sensor."""

        super().__init__(coordinator, router, description)
        self.entity_description: ARSensorDescription = description

    @property
    def native_value(
        self,
    ) -> float | str | None:
        """Return state."""

        description = self.entity_description
        state = self.coordinator.data.get(description.key)
        return state
