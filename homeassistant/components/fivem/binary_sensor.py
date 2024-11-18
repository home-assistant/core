"""The FiveM binary sensor platform."""

from dataclasses import dataclass

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN, NAME_STATUS
from .entity import FiveMEntity, FiveMEntityDescription


@dataclass(frozen=True)
class FiveMBinarySensorEntityDescription(
    BinarySensorEntityDescription, FiveMEntityDescription
):
    """Describes FiveM binary sensor entity."""


BINARY_SENSORS: tuple[FiveMBinarySensorEntityDescription, ...] = (
    FiveMBinarySensorEntityDescription(
        key=NAME_STATUS,
        translation_key="status",
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
