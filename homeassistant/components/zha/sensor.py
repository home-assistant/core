"""Sensors on Zigbee Home Automation networks."""

from __future__ import annotations

import logging
from typing import Any

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import StateType

from .entity import ZHAEntity
from .helpers import EntityData, get_zha_data

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the Zigbee Home Automation sensor from config entry."""
    zha_data = get_zha_data(hass)
    entities_to_create = zha_data.platforms.pop(Platform.SENSOR, [])
    entities = [Sensor(entity_data) for entity_data in entities_to_create]
    async_add_entities(entities)


# pylint: disable-next=hass-invalid-inheritance # needs fixing
class Sensor(ZHAEntity, SensorEntity):
    """ZHA sensor."""

    def __init__(self, entity_data: EntityData, **kwargs: Any) -> None:
        """Initialize the ZHA select entity."""
        super().__init__(entity_data, **kwargs)
        entity = self.entity_data.entity
        if (
            hasattr(entity, "_attr_device_class")
            and entity._attr_device_class is not None
        ):
            self._attr_device_class = SensorDeviceClass(entity._attr_device_class.value)
        if (
            hasattr(entity, "_attr_state_class")
            and entity._attr_state_class is not None
        ):
            self._attr_state_class = SensorStateClass(entity._attr_state_class.value)
        if (
            hasattr(entity, "_attr_native_unit_of_measurement")
            and entity._attr_native_unit_of_measurement is not None
        ):
            self._attr_native_unit_of_measurement = (
                entity._attr_native_unit_of_measurement
            )
        if hasattr(entity, "entity_description"):
            self.entity_description = entity.entity_description

    @property
    def native_value(self) -> StateType:
        """Return the state of the entity."""
        return self.entity_data.entity.native_value
