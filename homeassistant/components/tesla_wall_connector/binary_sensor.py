"""Binary Sensors for Tesla Wall Connector."""
from dataclasses import dataclass
import logging

from homeassistant.components.binary_sensor import (
    DEVICE_CLASS_BATTERY_CHARGING,
    DEVICE_CLASS_PLUG,
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.const import ENTITY_CATEGORY_DIAGNOSTIC

from . import (
    WallConnectorEntity,
    WallConnectorLambdaValueGetterMixin,
    prefix_entity_name,
)
from .const import DOMAIN, WALLCONNECTOR_DATA_VITALS

_LOGGER = logging.getLogger(__name__)


@dataclass
class WallConnectorBinarySensorDescription(
    BinarySensorEntityDescription, WallConnectorLambdaValueGetterMixin
):
    """Binary Sensor entity description."""


wall_connector_sensors = [
    WallConnectorBinarySensorDescription(
        key="vehicle_connected",
        name=prefix_entity_name("Vehicle connected"),
        entity_category=ENTITY_CATEGORY_DIAGNOSTIC,
        value_getter=lambda data: data[WALLCONNECTOR_DATA_VITALS].vehicle_connected,
        device_class=DEVICE_CLASS_PLUG,
    ),
    WallConnectorBinarySensorDescription(
        key="contactor_closed",
        name=prefix_entity_name("Contactor closed"),
        entity_category=ENTITY_CATEGORY_DIAGNOSTIC,
        value_getter=lambda data: data[WALLCONNECTOR_DATA_VITALS].contactor_closed,
        device_class=DEVICE_CLASS_BATTERY_CHARGING,
    ),
]


async def async_setup_entry(hass, config_entry, async_add_devices):
    """Create the Wall Connector sensor devices."""
    wall_connector = hass.data[DOMAIN][config_entry.entry_id]

    all_entities = []
    for description in wall_connector_sensors:
        entity = WallConnectorBinarySensorEntity(wall_connector, description)
        if entity is not None:
            all_entities.append(entity)

    async_add_devices(all_entities)


class WallConnectorBinarySensorEntity(WallConnectorEntity, BinarySensorEntity):
    """Wall Connector Sensor Entity."""

    def __init__(
        self, wall_connector: dict, description: WallConnectorBinarySensorDescription
    ) -> None:
        """Initialize WallConnectorBinarySensorEntity."""
        self.entity_description = description
        super().__init__(wall_connector)

    @property
    def state(self):
        """Return the state of the sensor."""
        if self.coordinator.data is None:
            return None

        return self.entity_description.value_getter(self.coordinator.data)
