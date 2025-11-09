"""Support for EnOcean binary sensors."""

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


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: EnOceanConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up entry."""
    gateway = config_entry.runtime_data.gateway

    for entity_id, properties in gateway.binary_sensor_entities:
        async_add_entities(
            [
                EnOceanBinarySensor(
                    entity_id, gateway=gateway, device_class=properties.device_class
                )
            ]
        )


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
        self.gateway.register_binary_sensor_callback(self.entity_id, self.update)

    @property
    def device_class(self) -> BinarySensorDeviceClass | None:
        """Return the class of this sensor."""
        return self._attr_device_class

    def update(self, is_on: bool) -> None:
        """Update the binary sensor state."""
        self._attr_is_on = is_on
        self.schedule_update_ha_state()
