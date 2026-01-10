"""Support for EnOcean binary sensors."""

from homeassistant_enocean.entity_id import EnOceanEntityID
from homeassistant_enocean.entity_properties import HomeAssistantEntityProperties
from homeassistant_enocean.gateway import EnOceanHomeAssistantGateway

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .config_entry import EnOceanConfigEntry
from .entity import EnOceanEntity


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: EnOceanConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up entry."""
    gateway = config_entry.runtime_data.gateway

    for entity_id in gateway.binary_sensor_entities:
        properties: HomeAssistantEntityProperties = gateway.binary_sensor_entities[
            entity_id
        ]
        async_add_entities(
            [
                EnOceanBinarySensor(
                    entity_id,
                    gateway=gateway,
                    device_class=gateway.binary_sensor_entities[entity_id].device_class,
                    entity_category=properties.entity_category,
                )
            ]
        )


class EnOceanBinarySensor(EnOceanEntity, BinarySensorEntity):
    """Representation of EnOcean binary sensors."""

    def __init__(
        self,
        entity_id: EnOceanEntityID,
        gateway: EnOceanHomeAssistantGateway,
        device_class: BinarySensorDeviceClass | None = None,
        entity_category: str | None = None,
    ) -> None:
        """Initialize the EnOcean binary sensor."""
        super().__init__(
            enocean_entity_id=entity_id,
            gateway=gateway,
            entity_category=entity_category,
        )
        self._attr_device_class = device_class
        self.gateway.register_binary_sensor_callback(entity_id, self.update)

    def update(self, is_on: bool) -> None:
        """Update the binary sensor state."""
        self._attr_is_on = is_on
        self.schedule_update_ha_state()
