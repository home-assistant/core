"""Support for Netatmo binary sensors."""


from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
import logging
from typing import cast

import pyatmo

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import PERCENTAGE, STATE_CLOSED, STATE_OPEN, EntityCategory
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import StateType

from .const import (
    CONF_URL_ENERGY,
    CONF_URL_SECURITY,
    DOMAIN,
    NETATMO_CREATE_BATTERY,
    NETATMO_CREATE_DOOR_TAG,
    NETATMO_CREATE_SENSOR,
    NETATMO_CREATE_WEATHER_SENSOR,
    SIGNAL_NAME,
)
from .data_handler import HOME, NetatmoDevice, NetatmoRoom
from .entity import NetatmoModuleEntity, NetatmoRoomEntity

#from .helper import NetatmoArea

_LOGGER = logging.getLogger(__name__)

def process_category(category: StateType) -> BinarySensorDeviceClass | None:
    """Process category and return binary sensor type."""
    if not isinstance(category, str):
        return None
    if category == "door":
        return BinarySensorDeviceClass.DOOR
    #if category == "furniture"
        #return BinarySensorDeviceClass.FURNITURE
    if category == "garage":
        return BinarySensorDeviceClass.GARAGE_DOOR
    #if category == "gate"
        #return BinarySensorDeviceClass.GATE
    #if category == "other"
        #return BinarySensorDeviceClass.OPENING
    if category == "window":
        return BinarySensorDeviceClass.WINDOW
    return BinarySensorDeviceClass.OPENING

def process_rf(strength: StateType) -> str | None:
    """Process wifi signal strength and return string for display."""
    if not isinstance(strength, int):
        return None
    if strength >= 90:
        return "Low"
    if strength >= 76:
        return "Medium"
    if strength >= 60:
        return "High"
    return "Full"

def process_status(status: StateType) -> str | None:
    """Process door/window tag status."""
    if not isinstance(status, str):
        return None
    if status == "closed":
        return STATE_CLOSED
    if status == "open":
        return STATE_OPEN
    return None

def process_wifi(strength: StateType) -> str | None:
    """Process wifi signal strength and return string for display."""
    if not isinstance(strength, int):
        return None
    if strength >= 86:
        return "Low"
    if strength >= 71:
        return "Medium"
    if strength >= 56:
        return "High"
    return "Full"

@dataclass(frozen=True, kw_only=True)
class NetatmoBinarySensorEntityDescription(BinarySensorEntityDescription):
    """Describes Netatmo binary sensor entity."""

    netatmo_name: str
    value_fn: Callable[[StateType], StateType] = lambda x: x


BINARY_SENSOR_TYPES: tuple[NetatmoBinarySensorEntityDescription, ...] = (
    NetatmoBinarySensorEntityDescription(
        key="opening",
        netatmo_name="status",
        ###entity_category=EntityCategory.CONFIG,
        device_class=BinarySensorDeviceClass.OPENING,
        value_fn=process_status,
    ),
)

BINARY_SENSOR_TYPES_KEYS = [desc.key for desc in BINARY_SENSOR_TYPES]

@dataclass(frozen=True, kw_only=True)
class NetatmoSensorEntityDescription(SensorEntityDescription):
    """Describes Netatmo sensor entity."""

    netatmo_name: str
    value_fn: Callable[[StateType], StateType] = lambda x: x


SENSOR_TYPES: tuple[NetatmoSensorEntityDescription, ...] = (
    NetatmoSensorEntityDescription(
        key="battery_percent",
        netatmo_name="battery",
        entity_category=EntityCategory.DIAGNOSTIC,
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        device_class=SensorDeviceClass.BATTERY,
    ),
    NetatmoSensorEntityDescription(
        key="reachable",
        netatmo_name="reachable",
        entity_registry_enabled_default=False,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    NetatmoSensorEntityDescription(
        key="rf_status",
        netatmo_name="rf_strength",
        entity_registry_enabled_default=False,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=process_rf,
    ),
    NetatmoSensorEntityDescription(
        key="wifi_status",
        netatmo_name="wifi_strength",
        entity_registry_enabled_default=False,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=process_wifi,
    ),
)

SENSOR_TYPES_KEYS = [desc.key for desc in SENSOR_TYPES]

BATTERY_SENSOR_DESCRIPTION = NetatmoSensorEntityDescription(
    key="battery",
    netatmo_name="battery",
    entity_category=EntityCategory.DIAGNOSTIC,
    native_unit_of_measurement=PERCENTAGE,
    state_class=SensorStateClass.MEASUREMENT,
    device_class=SensorDeviceClass.BATTERY,
)


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up the Netatmo door_tag platform."""

    @callback
    def _create_battery_entity(netatmo_device: NetatmoDevice) -> None:
        if not hasattr(netatmo_device.device, "battery"):
            return
        entity = NetatmoDoorTagBatterySensor(netatmo_device)
        async_add_entities([entity])

    entry.async_on_unload(
        async_dispatcher_connect(hass, NETATMO_CREATE_BATTERY, _create_battery_entity)
    )

    @callback
    def _create_binary_sensor_entity(netatmo_device: NetatmoDevice) -> None:
        _LOGGER.debug(
            "Adding %s door_tag %s",
            netatmo_device.device.device_category,
            netatmo_device.device.name,
        )
        async_add_entities(
            NetatmoDoorTagBinarySensor(netatmo_device, description)
            for description in BINARY_SENSOR_TYPES
            if description.netatmo_name in netatmo_device.device.features
        )

    entry.async_on_unload(
        async_dispatcher_connect(
            hass, NETATMO_CREATE_WEATHER_SENSOR, _create_binary_sensor_entity
        )
    )

    @callback
    def _create_sensor_entity(netatmo_device: NetatmoDevice) -> None:
        _LOGGER.debug(
            "Adding %s sensor %s",
            netatmo_device.device.device_category,
            netatmo_device.device.name,
        )
        async_add_entities(
            NetatmoDoorTagSensor(netatmo_device, description)
            for description in SENSOR_TYPES
            if description.key in netatmo_device.device.features
        )

    entry.async_on_unload(
        async_dispatcher_connect(hass, NETATMO_CREATE_SENSOR, _create_sensor_entity)
    )

    @callback
    def _create_door_tag_entity(netatmo_device: NetatmoRoom) -> None:
        if not netatmo_device.room.opening_type:
            msg = f"No opening type found for this room: {netatmo_device.room.name}"
            _LOGGER.debug(msg)
            return
        async_add_entities(
            NetatmoRoomSensor(netatmo_device, description)
            for description in SENSOR_TYPES
            if description.key in netatmo_device.room.features
        )

    entry.async_on_unload(
        async_dispatcher_connect(
            hass, NETATMO_CREATE_DOOR_TAG, _create_door_tag_entity
        )
    )


class NetatmoDoorTagBinarySensor(NetatmoModuleEntity, BinarySensorEntity):
    """Implementation of a Netatmo door_tag sensor."""

    entity_description: NetatmoBinarySensorEntityDescription

    def __init__(
        self,
        netatmo_device: NetatmoDevice,
        description: NetatmoBinarySensorEntityDescription,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(netatmo_device)
        self.entity_description = description
        self._attr_translation_key = description.netatmo_name
        self._attr_unique_id = f"{self.device.entity_id}-{description.key}"

    @property
    def available(self) -> bool:
        """Return True if entity is available."""
        return (
            self.device.reachable
            or getattr(self.device, self.entity_description.netatmo_name) is not None
        )

    @callback
    def async_update_callback(self) -> None:
        """Update the entity's state."""
        value = cast(
            StateType, getattr(self.device, self.entity_description.netatmo_name)
        )
        if value is not None:
            value = self.entity_description.value_fn(value)
        self._attr_native_value = value
        self.async_write_ha_state()


class NetatmoDoorTagBatterySensor(NetatmoModuleEntity, SensorEntity):
    """Implementation of a Door Tag Battery sensor."""

    entity_description: NetatmoSensorEntityDescription
    device: pyatmo.modules.NRV
    _attr_configuration_url = CONF_URL_ENERGY

    def __init__(self, netatmo_device: NetatmoDevice) -> None:
        """Initialize the sensor."""
        super().__init__(netatmo_device)
        self.entity_description = BATTERY_SENSOR_DESCRIPTION

        self._publishers.extend(
            [
                {
                    "name": HOME,
                    "home_id": netatmo_device.device.home.entity_id,
                    SIGNAL_NAME: netatmo_device.signal_name,
                },
            ]
        )

        self._attr_unique_id = f"{netatmo_device.parent_id}-{self.device.entity_id}-{self.entity_description.key}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, netatmo_device.parent_id)},
            name=netatmo_device.device.name,
            manufacturer=self.device_description[0],
            model=self.device_description[1],
            configuration_url=self._attr_configuration_url,
        )

    @callback
    def async_update_callback(self) -> None:
        """Update the entity's state."""
        if not self.device.reachable:
            if self.available:
                self._attr_available = False
            return

        self._attr_available = True
        self._attr_native_value = self.device.battery


class NetatmoDoorTagSensor(NetatmoModuleEntity, BinarySensorEntity):
    """Implementation of a Netatmo sensor."""

    entity_description: NetatmoBinarySensorEntityDescription
    _attr_configuration_url = CONF_URL_SECURITY

    def __init__(
        self,
        netatmo_device: NetatmoDevice,
        description: NetatmoBinarySensorEntityDescription,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(netatmo_device)
        self.entity_description = description

        self._publishers.extend(
            [
                {
                    "name": HOME,
                    "home_id": self.home.entity_id,
                    SIGNAL_NAME: netatmo_device.signal_name,
                },
            ]
        )

        self._attr_unique_id = (
            f"{self.device.entity_id}-{self.device.entity_id}-{description.key}"
        )

    @callback
    def async_update_callback(self) -> None:
        """Update the entity's state."""
        if not self.device.reachable:
            if self.available:
                self._attr_available = False
            return

        if (state := getattr(self.device, self.entity_description.key)) is None:
            return

        self._attr_available = True
        self._attr_native_value = state

        self.async_write_ha_state()

class NetatmoRoomSensor(NetatmoRoomEntity, SensorEntity):
    """Implementation of a Netatmo room sensor (door_tag device???)."""

    entity_description: NetatmoSensorEntityDescription

    def __init__(
        self,
        netatmo_room: NetatmoRoom,
        description: NetatmoSensorEntityDescription,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(netatmo_room)
        self.entity_description = description

        self._publishers.extend(
            [
                {
                    "name": HOME,
                    "home_id": self.home.entity_id,
                    SIGNAL_NAME: netatmo_room.signal_name,
                },
            ]
        )

        self._attr_unique_id = (
            f"{self.device.entity_id}-{self.device.entity_id}-{description.key}"
        )

    @callback
    def async_update_callback(self) -> None:
        """Update the entity's state."""
        if (state := getattr(self.device, self.entity_description.key)) is None:
            return

        self._attr_native_value = state

        self.async_write_ha_state()
