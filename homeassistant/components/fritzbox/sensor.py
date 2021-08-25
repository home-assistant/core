"""Support for AVM FRITZ!SmartHome temperature sensor only devices."""
from __future__ import annotations

from homeassistant.components.fritzbox.model import FritzSensorEntityDescription
from homeassistant.components.sensor import SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import FritzBoxEntity
from .const import CONF_COORDINATOR, DOMAIN as FRITZBOX_DOMAIN, SENSOR_TYPES


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up the FRITZ!SmartHome sensor from ConfigEntry."""
    entities: list[FritzBoxEntity] = []
    coordinator = hass.data[FRITZBOX_DOMAIN][entry.entry_id][CONF_COORDINATOR]

    for ain, device in coordinator.data.items():
        for description in SENSOR_TYPES:
            if description.suitable(device):
                entities.append(
                    FritzBoxSensor(
                        coordinator,
                        ain,
                        description,
                    )
                )
    async_add_entities(entities)


class FritzBoxSensor(FritzBoxEntity, SensorEntity):
    """The entity class for FRITZ!SmartHome sensors."""

    entity_description: FritzSensorEntityDescription

    @property
    def native_value(self) -> float | int | None:
        """Return the state of the sensor."""
        return self.entity_description.native_value(self.device)
