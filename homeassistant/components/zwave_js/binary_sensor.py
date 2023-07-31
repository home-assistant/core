"""Representation of Z-Wave binary sensors."""
from __future__ import annotations

from dataclasses import dataclass

from zwave_js_server.client import Client as ZwaveClient
from zwave_js_server.const import CommandClass
from zwave_js_server.const.command_class.lock import DOOR_STATUS_PROPERTY
from zwave_js_server.const.command_class.notification import (
    CC_SPECIFIC_NOTIFICATION_TYPE,
)
from zwave_js_server.model.driver import Driver

from homeassistant.components.binary_sensor import (
    DOMAIN as BINARY_SENSOR_DOMAIN,
    BinarySensorDeviceClass,
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DATA_CLIENT, DOMAIN
from .discovery import ZwaveDiscoveryInfo
from .entity import ZWaveBaseEntity

PARALLEL_UPDATES = 0


NOTIFICATION_SMOKE_ALARM = "1"
NOTIFICATION_CARBON_MONOOXIDE = "2"
NOTIFICATION_CARBON_DIOXIDE = "3"
NOTIFICATION_HEAT = "4"
NOTIFICATION_WATER = "5"
NOTIFICATION_ACCESS_CONTROL = "6"
NOTIFICATION_HOME_SECURITY = "7"
NOTIFICATION_POWER_MANAGEMENT = "8"
NOTIFICATION_SYSTEM = "9"
NOTIFICATION_EMERGENCY = "10"
NOTIFICATION_CLOCK = "11"
NOTIFICATION_APPLIANCE = "12"
NOTIFICATION_HOME_HEALTH = "13"
NOTIFICATION_SIREN = "14"
NOTIFICATION_WATER_VALVE = "15"
NOTIFICATION_WEATHER = "16"
NOTIFICATION_IRRIGATION = "17"
NOTIFICATION_GAS = "18"


@dataclass
class NotificationZWaveJSEntityDescription(BinarySensorEntityDescription):
    """Represent a Z-Wave JS binary sensor entity description."""

    off_state: str = "0"
    states: tuple[str, ...] | None = None


@dataclass
class PropertyZWaveJSMixin:
    """Represent the mixin for property sensor descriptions."""

    on_states: tuple[str, ...]


@dataclass
class PropertyZWaveJSEntityDescription(
    BinarySensorEntityDescription, PropertyZWaveJSMixin
):
    """Represent the entity description for property name sensors."""


# Mappings for Notification sensors
# https://github.com/zwave-js/node-zwave-js/blob/master/packages/config/config/notifications.json
NOTIFICATION_SENSOR_MAPPINGS: tuple[NotificationZWaveJSEntityDescription, ...] = (
    NotificationZWaveJSEntityDescription(
        # NotificationType 1: Smoke Alarm - State Id's 1 and 2 - Smoke detected
        key=NOTIFICATION_SMOKE_ALARM,
        states=("1", "2"),
        device_class=BinarySensorDeviceClass.SMOKE,
    ),
    NotificationZWaveJSEntityDescription(
        # NotificationType 1: Smoke Alarm - All other State Id's
        key=NOTIFICATION_SMOKE_ALARM,
        device_class=BinarySensorDeviceClass.PROBLEM,
    ),
    NotificationZWaveJSEntityDescription(
        # NotificationType 2: Carbon Monoxide - State Id's 1 and 2
        key=NOTIFICATION_CARBON_MONOOXIDE,
        states=("1", "2"),
        device_class=BinarySensorDeviceClass.CO,
    ),
    NotificationZWaveJSEntityDescription(
        # NotificationType 2: Carbon Monoxide - All other State Id's
        key=NOTIFICATION_CARBON_MONOOXIDE,
        device_class=BinarySensorDeviceClass.PROBLEM,
    ),
    NotificationZWaveJSEntityDescription(
        # NotificationType 3: Carbon Dioxide - State Id's 1 and 2
        key=NOTIFICATION_CARBON_DIOXIDE,
        states=("1", "2"),
        device_class=BinarySensorDeviceClass.GAS,
    ),
    NotificationZWaveJSEntityDescription(
        # NotificationType 3: Carbon Dioxide - All other State Id's
        key=NOTIFICATION_CARBON_DIOXIDE,
        device_class=BinarySensorDeviceClass.PROBLEM,
    ),
    NotificationZWaveJSEntityDescription(
        # NotificationType 4: Heat - State Id's 1, 2, 5, 6 (heat/underheat)
        key=NOTIFICATION_HEAT,
        states=("1", "2", "5", "6"),
        device_class=BinarySensorDeviceClass.HEAT,
    ),
    NotificationZWaveJSEntityDescription(
        # NotificationType 4: Heat - All other State Id's
        key=NOTIFICATION_HEAT,
        device_class=BinarySensorDeviceClass.PROBLEM,
    ),
    NotificationZWaveJSEntityDescription(
        # NotificationType 5: Water - State Id's 1, 2, 3, 4
        key=NOTIFICATION_WATER,
        states=("1", "2", "3", "4"),
        device_class=BinarySensorDeviceClass.MOISTURE,
    ),
    NotificationZWaveJSEntityDescription(
        # NotificationType 5: Water - All other State Id's
        key=NOTIFICATION_WATER,
        device_class=BinarySensorDeviceClass.PROBLEM,
    ),
    NotificationZWaveJSEntityDescription(
        # NotificationType 6: Access Control - State Id's 1, 2, 3, 4 (Lock)
        key=NOTIFICATION_ACCESS_CONTROL,
        states=("1", "2", "3", "4"),
        device_class=BinarySensorDeviceClass.LOCK,
    ),
    NotificationZWaveJSEntityDescription(
        # NotificationType 6: Access Control - State Id's 11 (Lock jammed)
        key=NOTIFICATION_ACCESS_CONTROL,
        states=("11",),
        device_class=BinarySensorDeviceClass.PROBLEM,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    NotificationZWaveJSEntityDescription(
        # NotificationType 6: Access Control - State Id 22 (door/window open)
        key=NOTIFICATION_ACCESS_CONTROL,
        off_state="23",
        states=("22", "23"),
        device_class=BinarySensorDeviceClass.DOOR,
    ),
    NotificationZWaveJSEntityDescription(
        # NotificationType 7: Home Security - State Id's 1, 2 (intrusion)
        key=NOTIFICATION_HOME_SECURITY,
        states=("1", "2"),
        device_class=BinarySensorDeviceClass.SAFETY,
    ),
    NotificationZWaveJSEntityDescription(
        # NotificationType 7: Home Security - State Id's 3, 4, 9 (tampering)
        key=NOTIFICATION_HOME_SECURITY,
        states=("3", "4", "9"),
        device_class=BinarySensorDeviceClass.TAMPER,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    NotificationZWaveJSEntityDescription(
        # NotificationType 7: Home Security - State Id's 5, 6 (glass breakage)
        key=NOTIFICATION_HOME_SECURITY,
        states=("5", "6"),
        device_class=BinarySensorDeviceClass.SAFETY,
    ),
    NotificationZWaveJSEntityDescription(
        # NotificationType 7: Home Security - State Id's 7, 8 (motion)
        key=NOTIFICATION_HOME_SECURITY,
        states=("7", "8"),
        device_class=BinarySensorDeviceClass.MOTION,
    ),
    NotificationZWaveJSEntityDescription(
        # NotificationType 8: Power Management -
        # State Id's 2, 3 (Mains status)
        key=NOTIFICATION_POWER_MANAGEMENT,
        off_state="2",
        states=("2", "3"),
        device_class=BinarySensorDeviceClass.PLUG,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    NotificationZWaveJSEntityDescription(
        # NotificationType 8: Power Management -
        # State Id's 6, 7, 8, 9 (power status)
        key=NOTIFICATION_POWER_MANAGEMENT,
        states=("6", "7", "8", "9"),
        device_class=BinarySensorDeviceClass.SAFETY,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    NotificationZWaveJSEntityDescription(
        # NotificationType 8: Power Management -
        # State Id's 10, 11, 17 (Battery maintenance status)
        key=NOTIFICATION_POWER_MANAGEMENT,
        states=("10", "11", "17"),
        device_class=BinarySensorDeviceClass.BATTERY,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    NotificationZWaveJSEntityDescription(
        # NotificationType 9: System - State Id's 1, 2, 3, 4, 6, 7
        key=NOTIFICATION_SYSTEM,
        states=("1", "2", "3", "4", "6", "7"),
        device_class=BinarySensorDeviceClass.PROBLEM,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    NotificationZWaveJSEntityDescription(
        # NotificationType 10: Emergency - State Id's 1, 2, 3
        key=NOTIFICATION_EMERGENCY,
        states=("1", "2", "3"),
        device_class=BinarySensorDeviceClass.PROBLEM,
    ),
    NotificationZWaveJSEntityDescription(
        # NotificationType 14: Siren
        key=NOTIFICATION_SIREN,
        states=("1",),
        device_class=BinarySensorDeviceClass.SOUND,
    ),
    NotificationZWaveJSEntityDescription(
        # NotificationType 18: Gas
        key=NOTIFICATION_GAS,
        states=("1", "2", "3", "4"),
        device_class=BinarySensorDeviceClass.GAS,
    ),
    NotificationZWaveJSEntityDescription(
        # NotificationType 18: Gas
        key=NOTIFICATION_GAS,
        states=("6",),
        device_class=BinarySensorDeviceClass.PROBLEM,
    ),
)


# Mappings for property sensors
PROPERTY_SENSOR_MAPPINGS: dict[str, PropertyZWaveJSEntityDescription] = {
    DOOR_STATUS_PROPERTY: PropertyZWaveJSEntityDescription(
        key=DOOR_STATUS_PROPERTY,
        on_states=("open",),
        device_class=BinarySensorDeviceClass.DOOR,
    ),
}


# Mappings for boolean sensors
BOOLEAN_SENSOR_MAPPINGS: dict[int, BinarySensorEntityDescription] = {
    CommandClass.BATTERY: BinarySensorEntityDescription(
        key=str(CommandClass.BATTERY),
        device_class=BinarySensorDeviceClass.BATTERY,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
}


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
        driver = client.driver
        assert driver is not None  # Driver is ready before platforms are loaded.
        entities: list[BinarySensorEntity] = []

        if info.platform_hint == "notification":
            # Get all sensors from Notification CC states
            for state_key in info.primary_value.metadata.states:
                # ignore idle key (0)
                if state_key == "0":
                    continue

                notification_description: NotificationZWaveJSEntityDescription | None = (
                    None
                )

                for description in NOTIFICATION_SENSOR_MAPPINGS:
                    if (
                        int(description.key)
                        == info.primary_value.metadata.cc_specific[
                            CC_SPECIFIC_NOTIFICATION_TYPE
                        ]
                    ) and (not description.states or state_key in description.states):
                        notification_description = description
                        break

                if (
                    notification_description
                    and notification_description.off_state == state_key
                ):
                    continue

                entities.append(
                    ZWaveNotificationBinarySensor(
                        config_entry, driver, info, state_key, notification_description
                    )
                )
        elif (
            info.platform_hint == "property"
            and info.primary_value.property_name
            and (
                property_description := PROPERTY_SENSOR_MAPPINGS.get(
                    info.primary_value.property_name
                )
            )
        ):
            entities.append(
                ZWavePropertyBinarySensor(
                    config_entry, driver, info, property_description
                )
            )
        elif info.platform_hint == "config_parameter":
            entities.append(
                ZWaveConfigParameterBinarySensor(config_entry, driver, info)
            )
        else:
            # boolean sensor
            entities.append(ZWaveBooleanBinarySensor(config_entry, driver, info))

        async_add_entities(entities)

    config_entry.async_on_unload(
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
        driver: Driver,
        info: ZwaveDiscoveryInfo,
    ) -> None:
        """Initialize a ZWaveBooleanBinarySensor entity."""
        super().__init__(config_entry, driver, info)

        # Entity class attributes
        self._attr_name = self.generate_name(include_value_name=True)
        if description := BOOLEAN_SENSOR_MAPPINGS.get(
            self.info.primary_value.command_class
        ):
            self.entity_description = description

    @property
    def is_on(self) -> bool | None:
        """Return if the sensor is on or off."""
        if self.info.primary_value.value is None:
            return None
        return bool(self.info.primary_value.value)


class ZWaveNotificationBinarySensor(ZWaveBaseEntity, BinarySensorEntity):
    """Representation of a Z-Wave binary_sensor from Notification CommandClass."""

    def __init__(
        self,
        config_entry: ConfigEntry,
        driver: Driver,
        info: ZwaveDiscoveryInfo,
        state_key: str,
        description: NotificationZWaveJSEntityDescription | None = None,
    ) -> None:
        """Initialize a ZWaveNotificationBinarySensor entity."""
        super().__init__(config_entry, driver, info)
        self.state_key = state_key
        if description:
            self.entity_description = description

        # Entity class attributes
        self._attr_name = self.generate_name(
            alternate_value_name=self.info.primary_value.metadata.states[self.state_key]
        )
        self._attr_unique_id = f"{self._attr_unique_id}.{self.state_key}"

    @property
    def is_on(self) -> bool | None:
        """Return if the sensor is on or off."""
        if self.info.primary_value.value is None:
            return None
        return int(self.info.primary_value.value) == int(self.state_key)


class ZWavePropertyBinarySensor(ZWaveBaseEntity, BinarySensorEntity):
    """Representation of a Z-Wave binary_sensor from a property."""

    entity_description: PropertyZWaveJSEntityDescription

    def __init__(
        self,
        config_entry: ConfigEntry,
        driver: Driver,
        info: ZwaveDiscoveryInfo,
        description: PropertyZWaveJSEntityDescription,
    ) -> None:
        """Initialize a ZWavePropertyBinarySensor entity."""
        super().__init__(config_entry, driver, info)
        self.entity_description = description
        self._attr_name = self.generate_name(include_value_name=True)

    @property
    def is_on(self) -> bool | None:
        """Return if the sensor is on or off."""
        if self.info.primary_value.value is None:
            return None
        return self.info.primary_value.value in self.entity_description.on_states


class ZWaveConfigParameterBinarySensor(ZWaveBooleanBinarySensor):
    """Representation of a Z-Wave config parameter binary sensor."""

    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(
        self, config_entry: ConfigEntry, driver: Driver, info: ZwaveDiscoveryInfo
    ) -> None:
        """Initialize a ZWaveConfigParameterBinarySensor entity."""
        super().__init__(config_entry, driver, info)

        property_key_name = self.info.primary_value.property_key_name
        # Entity class attributes
        self._attr_name = self.generate_name(
            alternate_value_name=self.info.primary_value.property_name,
            additional_info=[property_key_name] if property_key_name else None,
        )
