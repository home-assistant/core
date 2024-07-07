"""Sensors on Zigbee Home Automation networks."""

from __future__ import annotations

import functools
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
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import StateType

from .entity import ZHAEntity
from .helpers import (
    SIGNAL_ADD_ENTITIES,
    EntityData,
    async_add_entities as zha_async_add_entities,
    get_zha_data,
)

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the Zigbee Home Automation sensor from config entry."""
    zha_data = get_zha_data(hass)
    entities_to_create = zha_data.platforms[Platform.SENSOR]

    unsub = async_dispatcher_connect(
        hass,
        SIGNAL_ADD_ENTITIES,
        functools.partial(
            zha_async_add_entities, async_add_entities, Sensor, entities_to_create
        ),
    )
    config_entry.async_on_unload(unsub)


# pylint: disable-next=hass-invalid-inheritance # needs fixing
class Sensor(ZHAEntity, SensorEntity):
    """ZHA sensor."""

    def __init__(self, entity_data: EntityData, **kwargs: Any) -> None:
        """Initialize the ZHA select entity."""
        super().__init__(entity_data, **kwargs)
        entity = self.entity_data.entity

        if entity.device_class is not None:
            self._attr_device_class = SensorDeviceClass(entity.device_class)

        if entity.state_class is not None:
            self._attr_state_class = SensorStateClass(entity.state_class)

        if hasattr(entity.info_object, "unit") and entity.info_object.unit is not None:
            self._attr_native_unit_of_measurement = entity.info_object.unit

        if (
            hasattr(entity, "entity_description")
            and entity.entity_description is not None
        ):
            entity_description = entity.entity_description

            if entity_description.state_class is not None:
                self._attr_state_class = SensorStateClass(
                    entity_description.state_class.value
                )

            if entity_description.scale is not None:
                self._attr_scale = entity_description.scale

            if entity_description.native_unit_of_measurement is not None:
                self._attr_native_unit_of_measurement = (
                    entity_description.native_unit_of_measurement
                )

            if entity_description.device_class is not None:
                self._attr_device_class = SensorDeviceClass(
                    entity_description.device_class.value
                )

    @property
    def native_value(self) -> StateType:
        """Return the state of the entity."""
        return self.entity_data.entity.native_value
