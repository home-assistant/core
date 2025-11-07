"""Support for EnOcean binary sensors."""

from __future__ import annotations

from homeassistant_enocean.entity_id import EnOceanEntityID
from homeassistant_enocean.gateway import EnOceanHomeAssistantGateway

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .config_entry import EnOceanConfigEntry
from .entity import EnOceanEntity

DEFAULT_NAME = ""
DEPENDENCIES = ["enocean"]
EVENT_BUTTON_PRESSED = "button_pressed"


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: EnOceanConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up entry."""
    gateway = config_entry.runtime_data.gateway

    for entity_id in gateway.binary_sensor_entities:
        async_add_entities([EnOceanBinarySensor(entity_id, gateway=gateway)])


class EnOceanBinarySensor(EnOceanEntity, BinarySensorEntity):
    """Representation of EnOcean binary sensors such as wall switches."""

    def __init__(
        self,
        entity_id: EnOceanEntityID,
        gateway: EnOceanHomeAssistantGateway,
        device_class: BinarySensorDeviceClass | None = None,
    ) -> None:
        """Initialize the EnOcean binary sensor."""
        super().__init__(enocean_entity_id=entity_id, gateway=gateway)
        self._attr_device_class = device_class

    @property
    def device_class(self) -> BinarySensorDeviceClass | None:
        """Return the class of this sensor."""
        return self._attr_device_class

    @property
    def is_on(self) -> bool | None:
        """Return true if the binary sensor is on."""
        is_on: bool | None = self.gateway.binary_sensor_is_on(self.enocean_entity_id)
        return is_on
