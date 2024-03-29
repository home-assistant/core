"""Binary sensors on Zigbee Home Automation networks."""

from __future__ import annotations

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .entity import ZHAEntity
from .helpers import get_zha_data


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the Zigbee Home Automation binary sensor from config entry."""
    zha_data = get_zha_data(hass)
    entities_to_create = zha_data.platforms.pop(Platform.BINARY_SENSOR, [])
    entities = [BinarySensor(entity_data) for entity_data in entities_to_create]
    async_add_entities(entities)


class BinarySensor(ZHAEntity, BinarySensorEntity):
    """ZHA BinarySensor."""

    _attribute_name: str

    def __init__(self, entity_data) -> None:
        """Initialize the ZHA binary sensor."""
        super().__init__(entity_data)
        if (
            hasattr(self.entity_data.entity, "_attr_device_class")
            and self.entity_data.entity._attr_device_class is not None
        ):
            self._attr_device_class = BinarySensorDeviceClass(
                self.entity_data.entity._attr_device_class.value
            )

    @property
    def is_on(self) -> bool:
        """Return True if the switch is on based on the state machine."""
        return self.entity_data.entity.is_on
