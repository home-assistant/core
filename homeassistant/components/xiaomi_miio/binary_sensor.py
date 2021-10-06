"""Support for Xiaomi Miio binary sensors."""
from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from enum import Enum

from homeassistant.components.binary_sensor import (
    DEVICE_CLASS_CONNECTIVITY,
    DEVICE_CLASS_PLUG,
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
    MODEL_FAN_ZA5,
    MODELS_HUMIDIFIER_MIIO,
    MODELS_HUMIDIFIER_MIOT,
    MODELS_HUMIDIFIER_MJJSQ,
)
from .device import XiaomiCoordinatedMiioEntity

ATTR_NO_WATER = "no_water"
ATTR_POWERSUPPLY_ATTACHED = "powersupply_attached"
ATTR_WATER_TANK_DETACHED = "water_tank_detached"


@dataclass
class XiaomiMiioBinarySensorDescription(BinarySensorEntityDescription):
    """A class that describes binary sensor entities."""

    value: Callable | None = None


BINARY_SENSOR_TYPES = (
    XiaomiMiioBinarySensorDescription(
        key=ATTR_NO_WATER,
        name="Water Tank Empty",
        icon="mdi:water-off-outline",
    ),
    XiaomiMiioBinarySensorDescription(
        key=ATTR_WATER_TANK_DETACHED,
        name="Water Tank",
        icon="mdi:car-coolant-level",
        device_class=DEVICE_CLASS_CONNECTIVITY,
        value=lambda value: not value,
    ),
    XiaomiMiioBinarySensorDescription(
        key=ATTR_POWERSUPPLY_ATTACHED,
        name="Power Supply",
        device_class=DEVICE_CLASS_PLUG,
    ),
)

FAN_ZA5_BINARY_SENSORS = (ATTR_POWERSUPPLY_ATTACHED,)
HUMIDIFIER_MIIO_BINARY_SENSORS = (ATTR_WATER_TANK_DETACHED,)
HUMIDIFIER_MIOT_BINARY_SENSORS = (ATTR_WATER_TANK_DETACHED,)
HUMIDIFIER_MJJSQ_BINARY_SENSORS = (ATTR_NO_WATER, ATTR_WATER_TANK_DETACHED)


async def async_setup_entry(hass, config_entry, async_add_entities):
    """Set up the Xiaomi sensor from a config entry."""
    entities = []

    if config_entry.data[CONF_FLOW_TYPE] == CONF_DEVICE:
        model = config_entry.data[CONF_MODEL]
        sensors = []
        if model in MODEL_FAN_ZA5:
            sensors = FAN_ZA5_BINARY_SENSORS
        elif model in MODELS_HUMIDIFIER_MIIO:
            sensors = HUMIDIFIER_MIIO_BINARY_SENSORS
        elif model in MODELS_HUMIDIFIER_MIOT:
            sensors = HUMIDIFIER_MIOT_BINARY_SENSORS
        elif model in MODELS_HUMIDIFIER_MJJSQ:
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
        state = self._extract_value_from_attribute(
            self.coordinator.data, self.entity_description.key
        )
        if self.entity_description.value is not None and state is not None:
            return self.entity_description.value(state)

        return state

    @staticmethod
    def _extract_value_from_attribute(state, attribute):
        value = getattr(state, attribute)
        if isinstance(value, Enum):
            return value.value

        return value
