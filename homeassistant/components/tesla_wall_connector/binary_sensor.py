"""Binary Sensors for Tesla Wall Connector."""
from dataclasses import dataclass
import logging

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import (
    WallConnectorData,
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


WALL_CONNECTOR_SENSORS = [
    WallConnectorBinarySensorDescription(
        key="vehicle_connected",
        name=prefix_entity_name("Vehicle connected"),
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda data: data[WALLCONNECTOR_DATA_VITALS].vehicle_connected,
        device_class=BinarySensorDeviceClass.PLUG,
    ),
    WallConnectorBinarySensorDescription(
        key="contactor_closed",
        name=prefix_entity_name("Contactor closed"),
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda data: data[WALLCONNECTOR_DATA_VITALS].contactor_closed,
        device_class=BinarySensorDeviceClass.BATTERY_CHARGING,
    ),
]


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_devices: AddEntitiesCallback,
) -> None:
    """Create the Wall Connector sensor devices."""
    wall_connector_data = hass.data[DOMAIN][config_entry.entry_id]

    all_entities = [
        WallConnectorBinarySensorEntity(wall_connector_data, description)
        for description in WALL_CONNECTOR_SENSORS
    ]

    async_add_devices(all_entities)


class WallConnectorBinarySensorEntity(WallConnectorEntity, BinarySensorEntity):
    """Wall Connector Sensor Entity."""

    def __init__(
        self,
        wall_connectord_data: WallConnectorData,
        description: WallConnectorBinarySensorDescription,
    ) -> None:
        """Initialize WallConnectorBinarySensorEntity."""
        self.entity_description = description
        super().__init__(wall_connectord_data)

    @property
    def is_on(self):
        """Return the state of the sensor."""

        return self.entity_description.value_fn(self.coordinator.data)
