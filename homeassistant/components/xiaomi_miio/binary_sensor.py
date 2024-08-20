"""Support for Xiaomi Miio binary sensors."""

from __future__ import annotations

from collections.abc import Callable, Iterable
from dataclasses import dataclass
import logging

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_DEVICE, CONF_MODEL, EntityCategory
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import VacuumCoordinatorDataAttributes
from .const import (
    CONF_FLOW_TYPE,
    DOMAIN,
    KEY_COORDINATOR,
    KEY_DEVICE,
    MODEL_AIRFRESH_A1,
    MODEL_AIRFRESH_T2017,
    MODEL_FAN_ZA5,
    MODELS_HUMIDIFIER_MIIO,
    MODELS_HUMIDIFIER_MIOT,
    MODELS_HUMIDIFIER_MJJSQ,
    MODELS_VACUUM,
    MODELS_VACUUM_WITH_MOP,
    MODELS_VACUUM_WITH_SEPARATE_MOP,
)
from .device import XiaomiCoordinatedMiioEntity

_LOGGER = logging.getLogger(__name__)

ATTR_NO_WATER = "no_water"
ATTR_PTC_STATUS = "ptc_status"
ATTR_POWERSUPPLY_ATTACHED = "powersupply_attached"
ATTR_WATER_TANK_DETACHED = "water_tank_detached"
ATTR_MOP_ATTACHED = "is_water_box_carriage_attached"
ATTR_WATER_BOX_ATTACHED = "is_water_box_attached"
ATTR_WATER_SHORTAGE = "is_water_shortage"


@dataclass(frozen=True)
class XiaomiMiioBinarySensorDescription(BinarySensorEntityDescription):
    """A class that describes binary sensor entities."""

    value: Callable | None = None
    parent_key: str | None = None


BINARY_SENSOR_TYPES = (
    XiaomiMiioBinarySensorDescription(
        key=ATTR_NO_WATER,
        name="Water tank empty",
        icon="mdi:water-off-outline",
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    XiaomiMiioBinarySensorDescription(
        key=ATTR_WATER_TANK_DETACHED,
        name="Water tank",
        icon="mdi:car-coolant-level",
        device_class=BinarySensorDeviceClass.CONNECTIVITY,
        value=lambda value: not value,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    XiaomiMiioBinarySensorDescription(
        key=ATTR_PTC_STATUS,
        name="Auxiliary heat status",
        device_class=BinarySensorDeviceClass.POWER,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    XiaomiMiioBinarySensorDescription(
        key=ATTR_POWERSUPPLY_ATTACHED,
        name="Power supply",
        device_class=BinarySensorDeviceClass.PLUG,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
)

AIRFRESH_A1_BINARY_SENSORS = (ATTR_PTC_STATUS,)
FAN_ZA5_BINARY_SENSORS = (ATTR_POWERSUPPLY_ATTACHED,)

VACUUM_SENSORS = {
    ATTR_MOP_ATTACHED: XiaomiMiioBinarySensorDescription(
        key=ATTR_WATER_BOX_ATTACHED,
        name="Mop attached",
        icon="mdi:square-rounded",
        parent_key=VacuumCoordinatorDataAttributes.status,
        entity_registry_enabled_default=True,
        device_class=BinarySensorDeviceClass.CONNECTIVITY,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    ATTR_WATER_BOX_ATTACHED: XiaomiMiioBinarySensorDescription(
        key=ATTR_WATER_BOX_ATTACHED,
        name="Water box attached",
        icon="mdi:water",
        parent_key=VacuumCoordinatorDataAttributes.status,
        entity_registry_enabled_default=True,
        device_class=BinarySensorDeviceClass.CONNECTIVITY,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    ATTR_WATER_SHORTAGE: XiaomiMiioBinarySensorDescription(
        key=ATTR_WATER_SHORTAGE,
        name="Water shortage",
        icon="mdi:water",
        parent_key=VacuumCoordinatorDataAttributes.status,
        entity_registry_enabled_default=True,
        device_class=BinarySensorDeviceClass.PROBLEM,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
}

VACUUM_SENSORS_SEPARATE_MOP = {
    **VACUUM_SENSORS,
    ATTR_MOP_ATTACHED: XiaomiMiioBinarySensorDescription(
        key=ATTR_MOP_ATTACHED,
        name="Mop attached",
        icon="mdi:square-rounded",
        parent_key=VacuumCoordinatorDataAttributes.status,
        entity_registry_enabled_default=True,
        device_class=BinarySensorDeviceClass.CONNECTIVITY,
        entity_category=EntityCategory.DIAGNOSTIC,
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
    coordinator = hass.data[DOMAIN][config_entry.entry_id][KEY_COORDINATOR]
    entities = []
    sensors = VACUUM_SENSORS

    if config_entry.data[CONF_MODEL] in MODELS_VACUUM_WITH_SEPARATE_MOP:
        sensors = VACUUM_SENSORS_SEPARATE_MOP

    for sensor, description in sensors.items():
        parent_key_data = getattr(coordinator.data, description.parent_key)
        if getattr(parent_key_data, description.key, None) is None:
            _LOGGER.debug(
                "It seems the %s does not support the %s as the initial value is None",
                config_entry.data[CONF_MODEL],
                description.key,
            )
            continue
        entities.append(
            XiaomiGenericBinarySensor(
                device,
                config_entry,
                f"{sensor}_{config_entry.unique_id}",
                coordinator,
                description,
            )
        )

    async_add_entities(entities)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the Xiaomi sensor from a config entry."""
    entities = []

    if config_entry.data[CONF_FLOW_TYPE] == CONF_DEVICE:
        model = config_entry.data[CONF_MODEL]
        sensors: Iterable[str] = []
        if model in MODEL_AIRFRESH_A1 or model in MODEL_AIRFRESH_T2017:
            sensors = AIRFRESH_A1_BINARY_SENSORS
        elif model in MODEL_FAN_ZA5:
            sensors = FAN_ZA5_BINARY_SENSORS
        elif model in MODELS_HUMIDIFIER_MIIO:
            sensors = HUMIDIFIER_MIIO_BINARY_SENSORS
        elif model in MODELS_HUMIDIFIER_MIOT:
            sensors = HUMIDIFIER_MIOT_BINARY_SENSORS
        elif model in MODELS_HUMIDIFIER_MJJSQ:
            sensors = HUMIDIFIER_MJJSQ_BINARY_SENSORS
        elif model in MODELS_VACUUM:
            _setup_vacuum_sensors(hass, config_entry, async_add_entities)
            return

        for description in BINARY_SENSOR_TYPES:
            if description.key not in sensors:
                continue
            entities.append(
                XiaomiGenericBinarySensor(
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

    entity_description: XiaomiMiioBinarySensorDescription

    def __init__(self, device, entry, unique_id, coordinator, description):
        """Initialize the entity."""
        super().__init__(device, entry, unique_id, coordinator)

        self.entity_description = description
        self._attr_entity_registry_enabled_default = (
            description.entity_registry_enabled_default
        )
        self._attr_is_on = self._determine_native_value()

    @callback
    def _handle_coordinator_update(self) -> None:
        self._attr_is_on = self._determine_native_value()

        super()._handle_coordinator_update()

    def _determine_native_value(self):
        """Determine native value."""
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
