"""Support for Xiaomi Miio binary sensors."""
from enum import Enum

from homeassistant.components.binary_sensor import (
    BinarySensorEntity,
    BinarySensorEntityDescription,
)

from .const import (
    CONF_DEVICE,
    CONF_FLOW_TYPE,
    CONF_MODEL,
    DOMAIN,
    KEY_COORDINATOR,
    KEY_DEVICE,
    MODELS_HUMIDIFIER_MJJSQ,
)
from .device import XiaomiCoordinatedMiioEntity

ATTR_NO_WATER = "no_water"
ATTR_WATER_TANK_DETACHED = "water_tank_detached"

BINARY_SENSOR_TYPES = (
    BinarySensorEntityDescription(
        key=ATTR_NO_WATER,
        name="Water Tank Empty",
        icon="mdi:water-off-outline",
    ),
    BinarySensorEntityDescription(
        key=ATTR_WATER_TANK_DETACHED,
        name="Water Tank Detached",
        icon="mdi:flask-empty-off-outline",
    ),
)

HUMIDIFIER_MJJSQ_BINARY_SENSORS = (ATTR_NO_WATER, ATTR_WATER_TANK_DETACHED)


async def async_setup_entry(hass, config_entry, async_add_entities):
    """Set up the Xiaomi sensor from a config entry."""
    entities = []

    if config_entry.data[CONF_FLOW_TYPE] == CONF_DEVICE:
        model = config_entry.data[CONF_MODEL]
        sensors = []
        if model in MODELS_HUMIDIFIER_MJJSQ:
            sensors = HUMIDIFIER_MJJSQ_BINARY_SENSORS
        for description in BINARY_SENSOR_TYPES:
            if description.key not in sensors:
                continue
            entities.append(
                XiaomiGenericBinarySensor(
                    f"{config_entry.title} {description.name}",
                    hass.data[DOMAIN][config_entry.entry_id][KEY_DEVICE],
                    config_entry,
                    f"{description.key}_{config_entry.unique_id}",
                    hass.data[DOMAIN][config_entry.entry_id][KEY_COORDINATOR],
                    description,
                )
            )

    async_add_entities(entities)


class XiaomiGenericBinarySensor(XiaomiCoordinatedMiioEntity, BinarySensorEntity):
    """Representation of a Xiaomi Humidifier binary sensor."""

    def __init__(self, name, device, entry, unique_id, coordinator, description):
        """Initialize the entity."""
        super().__init__(name, device, entry, unique_id, coordinator)

        self.entity_description = description

    @property
    def is_on(self):
        """Return true if the binary sensor is on."""
        return self._extract_value_from_attribute(
            self.coordinator.data, self.entity_description.key
        )

    @staticmethod
    def _extract_value_from_attribute(state, attribute):
        value = getattr(state, attribute)
        if isinstance(value, Enum):
            return value.value

        return value
