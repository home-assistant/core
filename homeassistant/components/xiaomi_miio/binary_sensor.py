"""Support for Xiaomi Miio binary sensors."""
from __future__ import annotations

from dataclasses import dataclass
import logging
from typing import Callable

from homeassistant.components.binary_sensor import (
    DEVICE_CLASS_CONNECTIVITY,
    DEVICE_CLASS_PROBLEM,
    BinarySensorEntity,
    BinarySensorEntityDescription,
)

from . import VacuumCoordinatorDataAttributes
from .const import (
    CONF_DEVICE,
    CONF_FLOW_TYPE,
    CONF_MODEL,
    DOMAIN,
    KEY_COORDINATOR,
    KEY_DEVICE,
    MODELS_HUMIDIFIER_MIIO,
    MODELS_HUMIDIFIER_MIOT,
    MODELS_HUMIDIFIER_MJJSQ,
    MODELS_VACUUM,
    MODELS_VACUUM_WITH_MOP,
)
from .device import XiaomiCoordinatedMiioEntity

_LOGGER = logging.getLogger(__name__)


ATTR_NO_WATER = "no_water"
ATTR_WATER_TANK_DETACHED = "water_tank_detached"
ATTR_MOP_ATTACHED = "is_water_box_carriage_attached"
ATTR_WATER_BOX_ATTACHED = "is_water_box_attached"
ATTR_WATER_SHORTAGE = "is_water_shortage"


@dataclass
class XiaomiMiioBinarySensorDescription(BinarySensorEntityDescription):
    """A class that describes binary sensor entities."""

    value: Callable | None = None
    parent_key: str | None = None


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
)

VACUUM_SENSORS = {
    ATTR_MOP_ATTACHED: XiaomiMiioBinarySensorDescription(
        key=ATTR_MOP_ATTACHED,
        name="Mop Attached",
        icon="mdi:square-rounded",
        parent_key=VacuumCoordinatorDataAttributes.status,
        entity_registry_enabled_default=True,
        device_class=DEVICE_CLASS_CONNECTIVITY,
    ),
    ATTR_WATER_BOX_ATTACHED: XiaomiMiioBinarySensorDescription(
        key=ATTR_WATER_BOX_ATTACHED,
        name="Water Box Attached",
        icon="mdi:water",
        parent_key=VacuumCoordinatorDataAttributes.status,
        entity_registry_enabled_default=True,
        device_class=DEVICE_CLASS_CONNECTIVITY,
    ),
    ATTR_WATER_SHORTAGE: XiaomiMiioBinarySensorDescription(
        key=ATTR_WATER_SHORTAGE,
        name="Water Shortage",
        icon="mdi:water",
        parent_key=VacuumCoordinatorDataAttributes.status,
        entity_registry_enabled_default=True,
        device_class=DEVICE_CLASS_PROBLEM,
    ),
}

HUMIDIFIER_MIIO_BINARY_SENSORS = (ATTR_WATER_TANK_DETACHED,)
HUMIDIFIER_MIOT_BINARY_SENSORS = (ATTR_WATER_TANK_DETACHED,)
HUMIDIFIER_MJJSQ_BINARY_SENSORS = (ATTR_NO_WATER, ATTR_WATER_TANK_DETACHED)


def _setup_vacuum_sensors(hass, config_entry, async_add_entities):
    """Only vacuums with mop should have binary sensor registered."""

    if config_entry.data[CONF_MODEL] not in MODELS_VACUUM_WITH_MOP:
        return

    device = hass.data[DOMAIN][config_entry.entry_id].get(KEY_DEVICE)
    entities = []

    for sensor, description in VACUUM_SENSORS.items():
        entities.append(
            XiaomiGenericBinarySensor(
                f"{config_entry.title} {description.name}",
                device,
                config_entry,
                f"{sensor}_{config_entry.unique_id}",
                hass.data[DOMAIN][config_entry.entry_id][KEY_COORDINATOR],
                description,
            )
        )

    async_add_entities(entities)


async def async_setup_entry(hass, config_entry, async_add_entities):
    """Set up the Xiaomi sensor from a config entry."""
    entities = []

    if config_entry.data[CONF_FLOW_TYPE] == CONF_DEVICE:
        model = config_entry.data[CONF_MODEL]
        sensors = []
        if model in MODELS_HUMIDIFIER_MIIO:
            sensors = HUMIDIFIER_MIIO_BINARY_SENSORS
        elif model in MODELS_HUMIDIFIER_MIOT:
            sensors = HUMIDIFIER_MIOT_BINARY_SENSORS
        elif model in MODELS_HUMIDIFIER_MJJSQ:
            sensors = HUMIDIFIER_MJJSQ_BINARY_SENSORS
        elif model in MODELS_VACUUM:
            return _setup_vacuum_sensors(hass, config_entry, async_add_entities)

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

        self.entity_description: XiaomiMiioBinarySensorDescription = description
        self._attr_entity_registry_enabled_default = (
            description.entity_registry_enabled_default
        )

    @property
    def is_on(self):
        """Return true if the binary sensor is on."""
        if self.entity_description.parent_key is not None:
            return self._extract_value_from_attribute(
                getattr(self.coordinator.data, self.entity_description.parent_key),
                self.entity_description.key,
            )

        state = self._extract_value_from_attribute(
            self.coordinator.data, self.entity_description.key
        )
        if self.entity_description.value is not None and state is not None:
            return self.entity_description.value(state)

        return state
