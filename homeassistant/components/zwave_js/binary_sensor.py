"""Representation of Z-Wave binary sensors."""

import logging
from typing import Callable, List, Optional, TypedDict

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
    DEVICE_CLASS_POWER,
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
    states: List[int]  # required
    device_class: str
    enabled: bool


# Mappings for Notification sensors
NOTIFICATION_SENSOR_MAPPINGS: List[NotificationSensorMapping] = [
    {
        # NotificationType 1: Smoke Alarm - State Id's 1 and 2
        # Assuming here that Value 1 and 2 are not present at the same time
        "type": NOTIFICATION_SMOKE_ALARM,
        "states": [1, 2],
        "device_class": DEVICE_CLASS_SMOKE,
    },
    {
        # NotificationType 1: Smoke Alarm - All other State Id's
        # Create as disabled sensors
        "type": NOTIFICATION_SMOKE_ALARM,
        "states": [3, 4, 5, 6, 7, 8],
        "device_class": DEVICE_CLASS_SMOKE,
        "enabled": False,
    },
    {
        # NotificationType 2: Carbon Monoxide - State Id's 1 and 2
        "type": NOTIFICATION_CARBON_MONOOXIDE,
        "states": [1, 2],
        "device_class": DEVICE_CLASS_GAS,
    },
    {
        # NotificationType 2: Carbon Monoxide - All other State Id's
        "type": NOTIFICATION_CARBON_MONOOXIDE,
        "states": [4, 5, 7],
        "device_class": DEVICE_CLASS_GAS,
        "enabled": False,
    },
    {
        # NotificationType 3: Carbon Dioxide - State Id's 1 and 2
        "type": NOTIFICATION_CARBON_DIOXIDE,
        "states": [1, 2],
        "device_class": DEVICE_CLASS_GAS,
    },
    {
        # NotificationType 3: Carbon Dioxide - All other State Id's
        "type": NOTIFICATION_CARBON_DIOXIDE,
        "states": [4, 5, 7],
        "device_class": DEVICE_CLASS_GAS,
        "enabled": False,
    },
    {
        # NotificationType 4: Heat - State Id's 1, 2, 5, 6 (heat/underheat)
        "type": NOTIFICATION_HEAT,
        "states": [1, 2, 5, 6],
        "device_class": DEVICE_CLASS_HEAT,
    },
    {
        # NotificationType 4: Heat - All other State Id's
        "type": NOTIFICATION_HEAT,
        "states": [3, 4, 8, 10, 11],
        "device_class": DEVICE_CLASS_HEAT,
        "enabled": False,
    },
    {
        # NotificationType 5: Water - State Id's 1, 2, 3, 4
        "type": NOTIFICATION_WATER,
        "states": [1, 2, 3, 4],
        "device_class": DEVICE_CLASS_MOISTURE,
    },
    {
        # NotificationType 5: Water - All other State Id's
        "type": NOTIFICATION_WATER,
        "states": [5],
        "device_class": DEVICE_CLASS_MOISTURE,
        "enabled": False,
    },
    {
        # NotificationType 6: Access Control - State Id's 1, 2, 3, 4 (Lock)
        "type": NOTIFICATION_ACCESS_CONTROL,
        "states": [1, 2, 3, 4],
        "device_class": DEVICE_CLASS_LOCK,
    },
    {
        # NotificationType 6: Access Control - State Id 22 (door/window open)
        "type": NOTIFICATION_ACCESS_CONTROL,
        "states": [22],
        "device_class": DEVICE_CLASS_DOOR,
    },
    {
        # NotificationType 7: Home Security - State Id's 1, 2 (intrusion)
        # Assuming that value 1 and 2 are not present at the same time
        "type": NOTIFICATION_HOME_SECURITY,
        "states": [1, 2],
        "device_class": DEVICE_CLASS_SAFETY,
    },
    {
        # NotificationType 7: Home Security - State Id's 3, 4, 9 (tampering)
        "type": NOTIFICATION_HOME_SECURITY,
        "states": [3, 4, 9],
        "device_class": DEVICE_CLASS_SAFETY,
    },
    {
        # NotificationType 7: Home Security - State Id's 5, 6 (glass breakage)
        # Assuming that value 5 and 6 are not present at the same time
        "type": NOTIFICATION_HOME_SECURITY,
        "states": [5, 6],
        "device_class": DEVICE_CLASS_SAFETY,
    },
    {
        # NotificationType 7: Home Security - State Id's 7, 8 (motion)
        "type": NOTIFICATION_HOME_SECURITY,
        "states": [7, 8],
        "device_class": DEVICE_CLASS_MOTION,
    },
    {
        # NotificationType 8: Power management - Values 1...9
        "type": NOTIFICATION_POWER_MANAGEMENT,
        "states": [1, 2, 3, 4, 5, 6, 7, 8, 9],
        "device_class": DEVICE_CLASS_POWER,
        "enabled": False,
    },
    {
        # NotificationType 8: Power management - Values 10...15
        # Battery values (mutually exclusive)
        "type": NOTIFICATION_POWER_MANAGEMENT,
        "states": [10, 11, 12, 13, 14, 15],
        "device_class": DEVICE_CLASS_BATTERY,
        "enabled": False,
    },
    {
        # NotificationType 9: System - State Id's 1, 2, 6, 7
        "type": NOTIFICATION_SYSTEM,
        "states": [1, 2, 6, 7],
        "device_class": DEVICE_CLASS_PROBLEM,
        "enabled": False,
    },
    {
        # NotificationType 10: Emergency - State Id's 1, 2, 3
        "type": NOTIFICATION_EMERGENCY,
        "states": [1, 2, 3],
        "device_class": DEVICE_CLASS_PROBLEM,
    },
    {
        # NotificationType 11: Clock - State Id's 1, 2
        "type": NOTIFICATION_CLOCK,
        "states": [1, 2],
        "enabled": False,
    },
    {
        # NotificationType 12: Appliance - All State Id's
        "type": NOTIFICATION_APPLIANCE,
        "states": list(range(1, 22)),
    },
    {
        # NotificationType 13: Home Health - State Id's 1,2,3,4,5
        "type": NOTIFICATION_APPLIANCE,
        "states": [1, 2, 3, 4, 5],
    },
    {
        # NotificationType 14: Siren
        "type": NOTIFICATION_SIREN,
        "states": [1],
        "device_class": DEVICE_CLASS_SOUND,
    },
    {
        # NotificationType 15: Water valve
        # ignore non-boolean values
        "type": NOTIFICATION_WATER_VALVE,
        "states": [3, 4],
        "device_class": DEVICE_CLASS_PROBLEM,
    },
    {
        # NotificationType 16: Weather
        "type": NOTIFICATION_WEATHER,
        "states": [1, 2],
        "device_class": DEVICE_CLASS_PROBLEM,
    },
    {
        # NotificationType 17: Irrigation
        # ignore non-boolean values
        "type": NOTIFICATION_IRRIGATION,
        "states": [1, 2, 3, 4, 5],
    },
    {
        # NotificationType 18: Gas
        "type": NOTIFICATION_GAS,
        "states": [1, 2, 3, 4],
        "device_class": DEVICE_CLASS_GAS,
    },
    {
        # NotificationType 18: Gas
        "type": NOTIFICATION_GAS,
        "states": [6],
        "device_class": DEVICE_CLASS_PROBLEM,
    },
]


async def async_setup_entry(
    hass: HomeAssistant, config_entry: ConfigEntry, async_add_entities: Callable
) -> None:
    """Set up Z-Wave binary sensor from config entry."""
    client: ZwaveClient = hass.data[DOMAIN][config_entry.entry_id][DATA_CLIENT]

    @callback
    def async_add_binary_sensor(info: ZwaveDiscoveryInfo) -> None:
        """Add Z-Wave Binary Sensor."""
        entities: List[ZWaveBaseEntity] = []

        if info.platform_hint == "notification":
            entities.append(ZWaveNotificationBinarySensor(config_entry, client, info))
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

    @property
    def is_on(self) -> bool:
        """Return if the sensor is on or off."""
        return bool(self.info.primary_value.value)

    @property
    def device_class(self) -> Optional[str]:
        """Return device class."""
        if self.info.primary_value.command_class == CommandClass.BATTERY:
            return DEVICE_CLASS_BATTERY
        return None

    @property
    def entity_registry_enabled_default(self) -> bool:
        """Return if the entity should be enabled when first added to the entity registry."""
        if self.info.primary_value.command_class == CommandClass.SENSOR_BINARY:
            # Legacy binary sensors are phased out (replaced by notification sensors)
            # Disable by default to not confuse users
            if self.info.node.device_class.generic != "Binary Sensor":
                return False
        return True


class ZWaveNotificationBinarySensor(ZWaveBaseEntity, BinarySensorEntity):
    """Representation of a Z-Wave binary_sensor from Notification CommandClass."""

    def __init__(
        self, config_entry: ConfigEntry, client: ZwaveClient, info: ZwaveDiscoveryInfo
    ) -> None:
        """Initialize a ZWaveNotificationBinarySensor entity."""
        super().__init__(config_entry, client, info)
        # check if we have a custom mapping for this value
        self._mapping_info = self._get_sensor_mapping()

    @property
    def is_on(self) -> bool:
        """Return if the sensor is on or off."""
        if self._mapping_info:
            return self.info.primary_value.value in self._mapping_info["states"]
        return bool(self.info.primary_value.value != 0)

    @property
    def device_class(self) -> Optional[str]:
        """Return device class."""
        return self._mapping_info.get("device_class")

    @property
    def entity_registry_enabled_default(self) -> bool:
        """Return if the entity should be enabled when first added to the entity registry."""
        # We hide some more advanced sensors by default to not overwhelm users
        if not self._mapping_info:
            # consider value for which we do not have a mapping as advanced.
            return False
        return self._mapping_info.get("enabled", True)

    @callback
    def _get_sensor_mapping(self) -> NotificationSensorMapping:
        """Try to get a device specific mapping for this sensor."""
        for mapping in NOTIFICATION_SENSOR_MAPPINGS:
            if mapping["type"] != int(
                self.info.primary_value.metadata.cc_specific["notificationType"]
            ):
                continue
            for state_key in self.info.primary_value.metadata.states:
                # make sure the key is int
                state_key = int(state_key)
                if state_key not in mapping["states"]:
                    continue
                # match found
                mapping_info = mapping.copy()
                return mapping_info
        return {}
