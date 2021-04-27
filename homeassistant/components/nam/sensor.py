"""Support for the Nettigo Air Monitor service."""
from __future__ import annotations

from typing import Any, Callable

from homeassistant.components.sensor import SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import NAMUpdateCoordinator
from .const import DOMAIN, SENSORS

PARALLEL_UPDATES = 1


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: Callable
) -> None:
    """Add a Nettigo Air Monitor entities from a config_entry."""
    coordinator = hass.data[DOMAIN][entry.entry_id]

    sensors = []
    for sensor in SENSORS:
        if sensor in coordinator.data:
            sensors.append(NAMSensor(coordinator, sensor))

    async_add_entities(sensors, False)


class NAMSensor(CoordinatorEntity, SensorEntity):
    """Define an Nettigo Air Monitor sensor."""

    def __init__(self, coordinator: NAMUpdateCoordinator, sensor_type: str) -> None:
        """Initialize."""
        super().__init__(coordinator)
        self.sensor_type = sensor_type

    @property
    def name(self) -> str:
        """Return the name."""
        return SENSORS[self.sensor_type][0]

    @property
    def state(self) -> Any:
        """Return the state."""
        return getattr(self.coordinator.data, self.sensor_type)

    @property
    def unit_of_measurement(self) -> str | None:
        """Return the unit the value is expressed in."""
        return SENSORS[self.sensor_type][1]

    @property
    def device_class(self) -> str | None:
        """Return the class of this sensor."""
        return SENSORS[self.sensor_type][2]

    @property
    def icon(self) -> str | None:
        """Return the icon."""
        return SENSORS[self.sensor_type][3]

    @property
    def entity_registry_enabled_default(self) -> bool:
        """Return if the entity should be enabled when first added to the entity registry."""
        return SENSORS[self.sensor_type][4]

    @property
    def unique_id(self) -> str:
        """Return a unique_id for this entity."""
        return f"{self.coordinator.unique_id}-{self.sensor_type}".lower()  # type: ignore[attr-defined]

    @property
    def device_info(self) -> Any:
        """Return the device info."""
        return self.coordinator.device_info  # type: ignore[attr-defined]

    @property
    def available(self) -> bool:
        """Return if entity is available."""
        available = super().available

        # For a short time after booting, the device does not return values for all
        # sensors. For this reason, we mark entities for which data is missing as
        # unavailable.
        return available and bool(
            getattr(self.coordinator.data, self.sensor_type, None)
        )
