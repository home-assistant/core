"""Representation of Z-Wave binary sensors."""
from __future__ import annotations

import logging
from typing import TypedDict

from zwave_js_server.client import Client as ZwaveClient
from zwave_js_server.const import CommandClass

from homeassistant.components.binary_sensor import (
    DEVICE_CLASS_BATTERY,
    DEVICE_CLASS_DOOR,
    DEVICE_CLASS_GAS,
    DEVICE_CLASS_HEAT,
    DEVICE_CLASS_LOCK,
    DEVICE_CLASS_MOISTURE,
    DEVICE_CLASS_MOTION,
    DEVICE_CLASS_PROBLEM,
    DEVICE_CLASS_SAFETY,
    DEVICE_CLASS_SMOKE,
    DEVICE_CLASS_SOUND,
    DOMAIN as BINARY_SENSOR_DOMAIN,
    BinarySensorEntity,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DATA_CLIENT, DATA_UNSUBSCRIBE, DOMAIN
from .discovery import ZwaveDiscoveryInfo
from .entity import ZWaveBaseEntity

LOGGER = logging.getLogger(__name__)


NOTIFICATION_SMOKE_ALARM = 1
NOTIFICATION_CARBON_MONOOXIDE = 2
NOTIFICATION_CARBON_DIOXIDE = 3
NOTIFICATION_HEAT = 4
NOTIFICATION_WATER = 5
NOTIFICATION_ACCESS_CONTROL = 6
NOTIFICATION_HOME_SECURITY = 7
NOTIFICATION_POWER_MANAGEMENT = 8
NOTIFICATION_SYSTEM = 9
NOTIFICATION_EMERGENCY = 10
NOTIFICATION_CLOCK = 11
NOTIFICATION_APPLIANCE = 12
NOTIFICATION_HOME_HEALTH = 13
NOTIFICATION_SIREN = 14
NOTIFICATION_WATER_VALVE = 15
NOTIFICATION_WEATHER = 16
NOTIFICATION_IRRIGATION = 17
NOTIFICATION_GAS = 18


class NotificationSensorMapping(TypedDict, total=False):
    """Represent a notification sensor mapping dict type."""

    type: int  # required
    states: list[str]
    device_class: str
    enabled: bool


# Mappings for Notification sensors
# https://github.com/zwave-js/node-zwave-js/blob/master/packages/config/config/notifications.json
NOTIFICATION_SENSOR_MAPPINGS: list[NotificationSensorMapping] = [
    {
        # NotificationType 1: Smoke Alarm - State Id's 1 and 2 - Smoke detected
        "type": NOTIFICATION_SMOKE_ALARM,
        "states": ["1", "2"],
        "device_class": DEVICE_CLASS_SMOKE,
    },
    {
        # NotificationType 1: Smoke Alarm - All other State Id's
        "type": NOTIFICATION_SMOKE_ALARM,
        "device_class": DEVICE_CLASS_PROBLEM,
    },
    {
        # NotificationType 2: Carbon Monoxide - State Id's 1 and 2
        "type": NOTIFICATION_CARBON_MONOOXIDE,
        "states": ["1", "2"],
        "device_class": DEVICE_CLASS_GAS,
    },
    {
        # NotificationType 2: Carbon Monoxide - All other State Id's
        "type": NOTIFICATION_CARBON_MONOOXIDE,
        "device_class": DEVICE_CLASS_PROBLEM,
    },
    {
        # NotificationType 3: Carbon Dioxide - State Id's 1 and 2
        "type": NOTIFICATION_CARBON_DIOXIDE,
        "states": ["1", "2"],
        "device_class": DEVICE_CLASS_GAS,
    },
    {
        # NotificationType 3: Carbon Dioxide - All other State Id's
        "type": NOTIFICATION_CARBON_DIOXIDE,
        "device_class": DEVICE_CLASS_PROBLEM,
    },
    {
        # NotificationType 4: Heat - State Id's 1, 2, 5, 6 (heat/underheat)
        "type": NOTIFICATION_HEAT,
        "states": ["1", "2", "5", "6"],
        "device_class": DEVICE_CLASS_HEAT,
    },
    {
        # NotificationType 4: Heat - All other State Id's
        "type": NOTIFICATION_HEAT,
        "device_class": DEVICE_CLASS_PROBLEM,
    },
    {
        # NotificationType 5: Water - State Id's 1, 2, 3, 4
        "type": NOTIFICATION_WATER,
        "states": ["1", "2", "3", "4"],
        "device_class": DEVICE_CLASS_MOISTURE,
    },
    {
        # NotificationType 5: Water - All other State Id's
        "type": NOTIFICATION_WATER,
        "device_class": DEVICE_CLASS_PROBLEM,
    },
    {
        # NotificationType 6: Access Control - State Id's 1, 2, 3, 4 (Lock)
        "type": NOTIFICATION_ACCESS_CONTROL,
        "states": ["1", "2", "3", "4"],
        "device_class": DEVICE_CLASS_LOCK,
    },
    {
        # NotificationType 6: Access Control - State Id 16 (door/window open)
        "type": NOTIFICATION_ACCESS_CONTROL,
        "states": ["22"],
        "device_class": DEVICE_CLASS_DOOR,
    },
    {
        # NotificationType 6: Access Control - State Id 17 (door/window closed)
        "type": NOTIFICATION_ACCESS_CONTROL,
        "states": ["23"],
        "enabled": False,
    },
    {
        # NotificationType 7: Home Security - State Id's 1, 2 (intrusion)
        "type": NOTIFICATION_HOME_SECURITY,
        "states": ["1", "2"],
        "device_class": DEVICE_CLASS_SAFETY,
    },
    {
        # NotificationType 7: Home Security - State Id's 3, 4, 9 (tampering)
        "type": NOTIFICATION_HOME_SECURITY,
        "states": ["3", "4", "9"],
        "device_class": DEVICE_CLASS_SAFETY,
    },
    {
        # NotificationType 7: Home Security - State Id's 5, 6 (glass breakage)
        "type": NOTIFICATION_HOME_SECURITY,
        "states": ["5", "6"],
        "device_class": DEVICE_CLASS_SAFETY,
    },
    {
        # NotificationType 7: Home Security - State Id's 7, 8 (motion)
        "type": NOTIFICATION_HOME_SECURITY,
        "states": ["7", "8"],
        "device_class": DEVICE_CLASS_MOTION,
    },
    {
        # NotificationType 9: System - State Id's 1, 2, 6, 7
        "type": NOTIFICATION_SYSTEM,
        "states": ["1", "2", "6", "7"],
        "device_class": DEVICE_CLASS_PROBLEM,
    },
    {
        # NotificationType 10: Emergency - State Id's 1, 2, 3
        "type": NOTIFICATION_EMERGENCY,
        "states": ["1", "2", "3"],
        "device_class": DEVICE_CLASS_PROBLEM,
    },
    {
        # NotificationType 14: Siren
        "type": NOTIFICATION_SIREN,
        "states": ["1"],
        "device_class": DEVICE_CLASS_SOUND,
    },
    {
        # NotificationType 18: Gas
        "type": NOTIFICATION_GAS,
        "states": ["1", "2", "3", "4"],
        "device_class": DEVICE_CLASS_GAS,
    },
    {
        # NotificationType 18: Gas
        "type": NOTIFICATION_GAS,
        "states": ["6"],
        "device_class": DEVICE_CLASS_PROBLEM,
    },
]


PROPERTY_DOOR_STATUS = "doorStatus"


class PropertySensorMapping(TypedDict, total=False):
    """Represent a property sensor mapping dict type."""

    property_name: str  # required
    on_states: list[str]  # required
    device_class: str
    enabled: bool


# Mappings for property sensors
PROPERTY_SENSOR_MAPPINGS: list[PropertySensorMapping] = [
    {
        "property_name": PROPERTY_DOOR_STATUS,
        "on_states": ["open"],
        "device_class": DEVICE_CLASS_DOOR,
        "enabled": True,
    },
]


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Z-Wave binary sensor from config entry."""
    client: ZwaveClient = hass.data[DOMAIN][config_entry.entry_id][DATA_CLIENT]

    @callback
    def async_add_binary_sensor(info: ZwaveDiscoveryInfo) -> None:
        """Add Z-Wave Binary Sensor."""
        entities: list[BinarySensorEntity] = []

        if info.platform_hint == "notification":
            # Get all sensors from Notification CC states
            for state_key in info.primary_value.metadata.states:
                # ignore idle key (0)
                if state_key == "0":
                    continue
                entities.append(
                    ZWaveNotificationBinarySensor(config_entry, client, info, state_key)
                )
        elif info.platform_hint == "property":
            entities.append(ZWavePropertyBinarySensor(config_entry, client, info))
        else:
            # boolean sensor
            entities.append(ZWaveBooleanBinarySensor(config_entry, client, info))

        async_add_entities(entities)

    hass.data[DOMAIN][config_entry.entry_id][DATA_UNSUBSCRIBE].append(
        async_dispatcher_connect(
            hass,
            f"{DOMAIN}_{config_entry.entry_id}_add_{BINARY_SENSOR_DOMAIN}",
            async_add_binary_sensor,
        )
    )


class ZWaveBooleanBinarySensor(ZWaveBaseEntity, BinarySensorEntity):
    """Representation of a Z-Wave binary_sensor."""

    def __init__(
        self,
        config_entry: ConfigEntry,
        client: ZwaveClient,
        info: ZwaveDiscoveryInfo,
    ) -> None:
        """Initialize a ZWaveBooleanBinarySensor entity."""
        super().__init__(config_entry, client, info)
        self._name = self.generate_name(include_value_name=True)

    @property
    def is_on(self) -> bool | None:
        """Return if the sensor is on or off."""
        if self.info.primary_value.value is None:
            return None
        return bool(self.info.primary_value.value)

    @property
    def device_class(self) -> str | None:
        """Return device class."""
        if self.info.primary_value.command_class == CommandClass.BATTERY:
            return DEVICE_CLASS_BATTERY
        return None

    @property
    def entity_registry_enabled_default(self) -> bool:
        """Return if the entity should be enabled when first added to the entity registry."""
        # Legacy binary sensors are phased out (replaced by notification sensors)
        # Disable by default to not confuse users
        return bool(
            self.info.primary_value.command_class != CommandClass.SENSOR_BINARY
            or self.info.node.device_class.generic.key == 0x20
        )


class ZWaveNotificationBinarySensor(ZWaveBaseEntity, BinarySensorEntity):
    """Representation of a Z-Wave binary_sensor from Notification CommandClass."""

    def __init__(
        self,
        config_entry: ConfigEntry,
        client: ZwaveClient,
        info: ZwaveDiscoveryInfo,
        state_key: str,
    ) -> None:
        """Initialize a ZWaveNotificationBinarySensor entity."""
        super().__init__(config_entry, client, info)
        self.state_key = state_key
        self._name = self.generate_name(
            include_value_name=True,
            alternate_value_name=self.info.primary_value.property_name,
            additional_info=[self.info.primary_value.metadata.states[self.state_key]],
        )
        # check if we have a custom mapping for this value
        self._mapping_info = self._get_sensor_mapping()

    @property
    def is_on(self) -> bool | None:
        """Return if the sensor is on or off."""
        if self.info.primary_value.value is None:
            return None
        return int(self.info.primary_value.value) == int(self.state_key)

    @property
    def device_class(self) -> str | None:
        """Return device class."""
        return self._mapping_info.get("device_class")

    @property
    def unique_id(self) -> str:
        """Return unique id for this entity."""
        return f"{super().unique_id}.{self.state_key}"

    @property
    def entity_registry_enabled_default(self) -> bool:
        """Return if the entity should be enabled when first added to the entity registry."""
        if not self._mapping_info:
            return True
        return self._mapping_info.get("enabled", True)

    @callback
    def _get_sensor_mapping(self) -> NotificationSensorMapping:
        """Try to get a device specific mapping for this sensor."""
        for mapping in NOTIFICATION_SENSOR_MAPPINGS:
            if (
                mapping["type"]
                != self.info.primary_value.metadata.cc_specific["notificationType"]
            ):
                continue
            if not mapping.get("states") or self.state_key in mapping["states"]:
                # match found
                return mapping
        return {}


class ZWavePropertyBinarySensor(ZWaveBaseEntity, BinarySensorEntity):
    """Representation of a Z-Wave binary_sensor from a property."""

    def __init__(
        self, config_entry: ConfigEntry, client: ZwaveClient, info: ZwaveDiscoveryInfo
    ) -> None:
        """Initialize a ZWavePropertyBinarySensor entity."""
        super().__init__(config_entry, client, info)
        # check if we have a custom mapping for this value
        self._mapping_info = self._get_sensor_mapping()
        self._name = self.generate_name(include_value_name=True)

    @property
    def is_on(self) -> bool | None:
        """Return if the sensor is on or off."""
        if self.info.primary_value.value is None:
            return None
        return self.info.primary_value.value in self._mapping_info["on_states"]

    @property
    def device_class(self) -> str | None:
        """Return device class."""
        return self._mapping_info.get("device_class")

    @property
    def entity_registry_enabled_default(self) -> bool:
        """Return if the entity should be enabled when first added to the entity registry."""
        # We hide some more advanced sensors by default to not overwhelm users
        # unless explicitly stated in a mapping, assume deisabled by default
        return self._mapping_info.get("enabled", False)

    @callback
    def _get_sensor_mapping(self) -> PropertySensorMapping:
        """Try to get a device specific mapping for this sensor."""
        mapping_info = PropertySensorMapping()
        for mapping in PROPERTY_SENSOR_MAPPINGS:
            if mapping["property_name"] == self.info.primary_value.property_name:
                mapping_info = mapping.copy()
                break

        return mapping_info
