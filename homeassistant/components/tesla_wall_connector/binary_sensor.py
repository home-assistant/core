"""Binary Sensors for Tesla Wall Connector."""

from dataclasses import dataclass
import logging

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import WALLCONNECTOR_DATA_VITALS
from .coordinator import WallConnectorConfigEntry, WallConnectorData
from .entity import WallConnectorEntity, WallConnectorLambdaValueGetterMixin

_LOGGER = logging.getLogger(__name__)


@dataclass(frozen=True)
class WallConnectorBinarySensorDescription(
    BinarySensorEntityDescription, WallConnectorLambdaValueGetterMixin
):
    """Binary Sensor entity description."""


WALL_CONNECTOR_SENSORS = [
    WallConnectorBinarySensorDescription(
        key="vehicle_connected",
        translation_key="vehicle_connected",
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda data: data[WALLCONNECTOR_DATA_VITALS].vehicle_connected,
        device_class=BinarySensorDeviceClass.PLUG,
    ),
    WallConnectorBinarySensorDescription(
        key="contactor_closed",
        translation_key="contactor_closed",
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda data: data[WALLCONNECTOR_DATA_VITALS].contactor_closed,
        device_class=BinarySensorDeviceClass.BATTERY_CHARGING,
    ),
]


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: WallConnectorConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Create the Wall Connector sensor devices."""
    wall_connector_data = config_entry.runtime_data

    all_entities = [
        WallConnectorBinarySensorEntity(wall_connector_data, description)
        for description in WALL_CONNECTOR_SENSORS
    ]

    async_add_entities(all_entities)


class WallConnectorBinarySensorEntity(WallConnectorEntity, BinarySensorEntity):
    """Wall Connector Sensor Entity."""

    entity_description: WallConnectorBinarySensorDescription

    def __init__(
        self,
        wall_connectord_data: WallConnectorData,
        description: WallConnectorBinarySensorDescription,
    ) -> None:
        """Initialize WallConnectorBinarySensorEntity."""
        self.entity_description = description
        super().__init__(wall_connectord_data)

    @property
    def is_on(self) -> bool:
        """Return the state of the sensor."""

        return self.entity_description.value_fn(self.coordinator.data)
