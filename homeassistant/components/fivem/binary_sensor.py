"""The FiveM binary sensor platform."""
from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import FiveMEntity, FiveMEntityDescription
from .const import DOMAIN, ICON_STATUS, NAME_STATUS


class FiveMBinarySensorEntityDescription(
    BinarySensorEntityDescription, FiveMEntityDescription
):
    """Describes FiveM binary sensor entity."""


BINARY_SENSORS: tuple[FiveMBinarySensorEntityDescription, ...] = (
    FiveMBinarySensorEntityDescription(
        key=NAME_STATUS,
        name=NAME_STATUS,
        icon=ICON_STATUS,
        device_class=BinarySensorDeviceClass.CONNECTIVITY,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the FiveM binary sensor platform."""
    coordinator = hass.data[DOMAIN][entry.entry_id]

    async_add_entities(
        [FiveMSensorEntity(coordinator, description) for description in BINARY_SENSORS]
    )


class FiveMSensorEntity(FiveMEntity, BinarySensorEntity):
    """Representation of a FiveM sensor base entity."""

    entity_description: FiveMBinarySensorEntityDescription

    @property
    def is_on(self) -> bool:
        """Return the state of the sensor."""
        return self.coordinator.data[self.entity_description.key]
