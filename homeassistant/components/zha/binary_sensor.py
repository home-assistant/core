"""Binary sensors on Zigbee Home Automation networks."""

from __future__ import annotations

import functools

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .entity import ZHAEntity
from .helpers import (
    SIGNAL_ADD_ENTITIES,
    EntityData,
    async_add_entities as zha_async_add_entities,
    get_zha_data,
)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the Zigbee Home Automation binary sensor from config entry."""
    zha_data = get_zha_data(hass)
    entities_to_create = zha_data.platforms[Platform.BINARY_SENSOR]

    unsub = async_dispatcher_connect(
        hass,
        SIGNAL_ADD_ENTITIES,
        functools.partial(
            zha_async_add_entities, async_add_entities, BinarySensor, entities_to_create
        ),
    )
    config_entry.async_on_unload(unsub)


class BinarySensor(ZHAEntity, BinarySensorEntity):
    """ZHA BinarySensor."""

    def __init__(self, entity_data: EntityData) -> None:
        """Initialize the ZHA binary sensor."""
        super().__init__(entity_data)
        if self.entity_data.entity.info_object.device_class is not None:
            self._attr_device_class = BinarySensorDeviceClass(
                self.entity_data.entity.info_object.device_class
            )

    @property
    def is_on(self) -> bool:
        """Return True if the switch is on based on the state machine."""
        return self.entity_data.entity.is_on
