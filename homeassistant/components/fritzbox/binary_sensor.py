"""Support for Fritzbox binary sensors."""
from __future__ import annotations

from pyfritzhome.fritzhomedevice import FritzhomeDevice

from homeassistant.components.binary_sensor import BinarySensorEntity
from homeassistant.components.fritzbox.model import FritzBinarySensorEntityDescription
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from . import FritzBoxEntity
from .const import BINARY_SENSOR_TYPES, CONF_COORDINATOR, DOMAIN as FRITZBOX_DOMAIN


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up the FRITZ!SmartHome binary sensor from ConfigEntry."""
    entities: list[FritzboxBinarySensor] = []
    coordinator = hass.data[FRITZBOX_DOMAIN][entry.entry_id][CONF_COORDINATOR]

    for ain, device in coordinator.data.items():
        for description in BINARY_SENSOR_TYPES:
            if description.suitable(device):
                entities.append(
                    FritzboxBinarySensor(
                        coordinator,
                        ain,
                        description,
                    )
                )

    async_add_entities(entities)


class FritzboxBinarySensor(FritzBoxEntity, BinarySensorEntity):
    """Representation of a binary FRITZ!SmartHome device."""

    entity_description: FritzBinarySensorEntityDescription

    def __init__(
        self,
        coordinator: DataUpdateCoordinator[dict[str, FritzhomeDevice]],
        ain: str,
        entity_description: FritzBinarySensorEntityDescription,
    ) -> None:
        """Initialize the FritzBox entity."""
        super().__init__(coordinator, ain, entity_description)
        self._attr_name = self.device.name
        self._attr_unique_id = ain

    @property
    def is_on(self) -> bool | None:
        """Return true if sensor is on."""
        return self.entity_description.is_on(self.device)
