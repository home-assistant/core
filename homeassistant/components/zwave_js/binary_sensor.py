"""Representation of Z-Wave binary sensors."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, cast

from zwave_js_server.const import CommandClass
from zwave_js_server.const.command_class.lock import DOOR_STATUS_PROPERTY
from zwave_js_server.const.command_class.notification import (
    CC_SPECIFIC_NOTIFICATION_TYPE,
    NotificationEvent,
    NotificationType,
    SmokeAlarmNotificationEvent,
)
from zwave_js_server.model.driver import Driver

from homeassistant.components.binary_sensor import (
    DOMAIN as BINARY_SENSOR_DOMAIN,
    BinarySensorDeviceClass,
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.const import EntityCategory, Platform
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import DOMAIN
from .entity import NewZwaveDiscoveryInfo, ZWaveBaseEntity
from .models import (
    NewZWaveDiscoverySchema,
    ValueType,
    ZwaveDiscoveryInfo,
    ZwaveJSConfigEntry,
    ZWaveValueDiscoverySchema,
)

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


@dataclass(frozen=True, kw_only=True)
class NotificationZWaveJSEntityDescription(BinarySensorEntityDescription):
    """Represent a Z-Wave JS binary sensor entity description."""

    not_states: set[NotificationEvent | int] = field(default_factory=lambda: {0})
    states: set[NotificationEvent | int] | None = None


@dataclass(frozen=True, kw_only=True)
class PropertyZWaveJSEntityDescription(BinarySensorEntityDescription):
    """Represent the entity description for property name sensors."""

    on_states: tuple[str, ...]


@dataclass(frozen=True, kw_only=True)
class NewNotificationZWaveJSEntityDescription(BinarySensorEntityDescription):
    """Represent a Z-Wave JS binary sensor entity description."""

    state_key: str


# Mappings for Notification sensors
# https://github.com/zwave-js/specs/blob/master/Registries/Notification%20Command%20Class%2C%20list%20of%20assigned%20Notifications.xlsx
#
# Mapping rules:
# The catch all description should not have a device class and be marked as diagnostic.
#
# The following notifications have been moved to diagnostic:
# Smoke Alarm
# - Alarm silenced
# - Replacement required
# - Replacement required, End-of-life
# - Maintenance required, planned periodic inspection
# - Maintenance required, dust in device
# CO Alarm
# - Carbon monoxide test
# - Replacement required
# - Replacement required, End-of-life
# - Alarm silenced
# - Maintenance required, planned periodic inspection
# CO2 Alarm
# - Carbon dioxide test
# - Replacement required
# - Replacement required, End-of-life
# - Alarm silenced
# - Maintenance required, planned periodic inspection
# Heat Alarm
# - Rapid temperature rise (location provided)
# - Rapid temperature rise
# - Rapid temperature fall (location provided)
# - Rapid temperature fall
# - Heat alarm test
# - Alarm silenced
# - Replacement required, End-of-life
# - Maintenance required, dust in device
# - Maintenance required, planned periodic inspection

# Water Alarm
# - Replace water filter
# - Sump pump failure


# This set can be removed once all notification sensors have been migrated
# to use the new discovery schema and we've removed the old discovery code.
MIGRATED_NOTIFICATION_TYPES = {
    NotificationType.SMOKE_ALARM,
}

NOTIFICATION_SENSOR_MAPPINGS: tuple[NotificationZWaveJSEntityDescription, ...] = (
    NotificationZWaveJSEntityDescription(
        # NotificationType 2: Carbon Monoxide - State Id's 1 and 2
        key=NOTIFICATION_CARBON_MONOOXIDE,
        states={1, 2},
        device_class=BinarySensorDeviceClass.CO,
    ),
    NotificationZWaveJSEntityDescription(
        # NotificationType 2: Carbon Monoxide - State Id 4, 5, 7
        key=NOTIFICATION_CARBON_MONOOXIDE,
        states={4, 5, 7},
        device_class=BinarySensorDeviceClass.PROBLEM,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    NotificationZWaveJSEntityDescription(
        # NotificationType 2: Carbon Monoxide - All other State Id's
        key=NOTIFICATION_CARBON_MONOOXIDE,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    NotificationZWaveJSEntityDescription(
        # NotificationType 3: Carbon Dioxide - State Id's 1 and 2
        key=NOTIFICATION_CARBON_DIOXIDE,
        states={1, 2},
        device_class=BinarySensorDeviceClass.GAS,
    ),
    NotificationZWaveJSEntityDescription(
        # NotificationType 3: Carbon Dioxide - State Id's 4, 5, 7
        key=NOTIFICATION_CARBON_DIOXIDE,
        states={4, 5, 7},
        device_class=BinarySensorDeviceClass.PROBLEM,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    NotificationZWaveJSEntityDescription(
        # NotificationType 3: Carbon Dioxide - All other State Id's
        key=NOTIFICATION_CARBON_DIOXIDE,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    NotificationZWaveJSEntityDescription(
        # NotificationType 4: Heat - State Id's 1, 2, 5, 6 (heat/underheat)
        key=NOTIFICATION_HEAT,
        states={1, 2, 5, 6},
        device_class=BinarySensorDeviceClass.HEAT,
    ),
    NotificationZWaveJSEntityDescription(
        # NotificationType 4: Heat - State ID's 8, A, B
        key=NOTIFICATION_HEAT,
        states={8, 10, 11},
        device_class=BinarySensorDeviceClass.PROBLEM,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    NotificationZWaveJSEntityDescription(
        # NotificationType 4: Heat - All other State Id's
        key=NOTIFICATION_HEAT,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    NotificationZWaveJSEntityDescription(
        # NotificationType 5: Water - State Id's 1, 2, 3, 4, 6, 7, 8, 9, 0A
        key=NOTIFICATION_WATER,
        states={1, 2, 3, 4, 6, 7, 8, 9, 10},
        device_class=BinarySensorDeviceClass.MOISTURE,
    ),
    NotificationZWaveJSEntityDescription(
        # NotificationType 5: Water - State Id's B
        key=NOTIFICATION_WATER,
        states={11},
        device_class=BinarySensorDeviceClass.PROBLEM,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    NotificationZWaveJSEntityDescription(
        # NotificationType 5: Water - All other State Id's
        key=NOTIFICATION_WATER,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    NotificationZWaveJSEntityDescription(
        # NotificationType 6: Access Control - State Id's 1, 2, 3, 4 (Lock)
        key=NOTIFICATION_ACCESS_CONTROL,
        states={1, 2, 3, 4},
        device_class=BinarySensorDeviceClass.LOCK,
    ),
    NotificationZWaveJSEntityDescription(
        # NotificationType 6: Access Control - State Id's 11 (Lock jammed)
        key=NOTIFICATION_ACCESS_CONTROL,
        states={11},
        device_class=BinarySensorDeviceClass.PROBLEM,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    NotificationZWaveJSEntityDescription(
        # NotificationType 6: Access Control - State Id 22 (door/window open)
        key=NOTIFICATION_ACCESS_CONTROL,
        not_states={23},
        states={22},
        device_class=BinarySensorDeviceClass.DOOR,
    ),
    NotificationZWaveJSEntityDescription(
        # NotificationType 7: Home Security - State Id's 1, 2 (intrusion)
        key=NOTIFICATION_HOME_SECURITY,
        states={1, 2},
        device_class=BinarySensorDeviceClass.SAFETY,
    ),
    NotificationZWaveJSEntityDescription(
        # NotificationType 7: Home Security - State Id's 3, 4, 9 (tampering)
        key=NOTIFICATION_HOME_SECURITY,
        states={3, 4, 9},
        device_class=BinarySensorDeviceClass.TAMPER,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    NotificationZWaveJSEntityDescription(
        # NotificationType 7: Home Security - State Id's 5, 6 (glass breakage)
        key=NOTIFICATION_HOME_SECURITY,
        states={5, 6},
        device_class=BinarySensorDeviceClass.SAFETY,
    ),
    NotificationZWaveJSEntityDescription(
        # NotificationType 7: Home Security - State Id's 7, 8 (motion)
        key=NOTIFICATION_HOME_SECURITY,
        states={7, 8},
        device_class=BinarySensorDeviceClass.MOTION,
    ),
    NotificationZWaveJSEntityDescription(
        # NotificationType 8: Power Management -
        # State Id's 2, 3 (Mains status)
        key=NOTIFICATION_POWER_MANAGEMENT,
        not_states={2},
        states={3},
        device_class=BinarySensorDeviceClass.PLUG,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    NotificationZWaveJSEntityDescription(
        # NotificationType 8: Power Management -
        # State Id's 6, 7, 8, 9 (power status)
        key=NOTIFICATION_POWER_MANAGEMENT,
        states={6, 7, 8, 9},
        device_class=BinarySensorDeviceClass.SAFETY,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    NotificationZWaveJSEntityDescription(
        # NotificationType 8: Power Management -
        # State Id's 10, 11, 17 (Battery maintenance status)
        key=NOTIFICATION_POWER_MANAGEMENT,
        states={10, 11, 17},
        device_class=BinarySensorDeviceClass.BATTERY,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    NotificationZWaveJSEntityDescription(
        # NotificationType 9: System - State Id's 1, 2, 3, 4, 6, 7
        key=NOTIFICATION_SYSTEM,
        states={1, 2, 3, 4, 6, 7},
        device_class=BinarySensorDeviceClass.PROBLEM,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    NotificationZWaveJSEntityDescription(
        # NotificationType 10: Emergency - State Id's 1, 2, 3
        key=NOTIFICATION_EMERGENCY,
        states={1, 2, 3},
        device_class=BinarySensorDeviceClass.PROBLEM,
    ),
    NotificationZWaveJSEntityDescription(
        # NotificationType 14: Siren
        key=NOTIFICATION_SIREN,
        states={1},
        device_class=BinarySensorDeviceClass.SOUND,
    ),
    NotificationZWaveJSEntityDescription(
        # NotificationType 18: Gas - State Id's 1, 2, 3, 4
        key=NOTIFICATION_GAS,
        states={1, 2, 3, 4},
        device_class=BinarySensorDeviceClass.GAS,
    ),
    NotificationZWaveJSEntityDescription(
        # NotificationType 18: Gas - State Id 6
        key=NOTIFICATION_GAS,
        states={6},
        device_class=BinarySensorDeviceClass.PROBLEM,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    NotificationZWaveJSEntityDescription(
        # NotificationType 18: Gas - All other State Id's
        key=NOTIFICATION_GAS,
        entity_category=EntityCategory.DIAGNOSTIC,
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
BOOLEAN_SENSOR_MAPPINGS: dict[tuple[int, int | str], BinarySensorEntityDescription] = {
    (CommandClass.BATTERY, "backup"): BinarySensorEntityDescription(
        key="battery_backup",
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
    ),
    (CommandClass.BATTERY, "disconnected"): BinarySensorEntityDescription(
        key="battery_disconnected",
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
    ),
    (CommandClass.BATTERY, "isLow"): BinarySensorEntityDescription(
        key="battery_is_low",
        device_class=BinarySensorDeviceClass.BATTERY,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    (CommandClass.BATTERY, "lowFluid"): BinarySensorEntityDescription(
        key="battery_low_fluid",
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
    ),
    (CommandClass.BATTERY, "overheating"): BinarySensorEntityDescription(
        key="battery_overheating",
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
    ),
    (CommandClass.BATTERY, "rechargeable"): BinarySensorEntityDescription(
        key="battery_rechargeable",
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
    ),
}


@callback
def is_valid_notification_binary_sensor(
    info: ZwaveDiscoveryInfo | NewZwaveDiscoveryInfo,
) -> bool | NotificationZWaveJSEntityDescription:
    """Return if the notification CC Value is valid as binary sensor."""
    if not info.primary_value.metadata.states:
        return False
    return len(info.primary_value.metadata.states) > 1


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ZwaveJSConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Z-Wave binary sensor from config entry."""
    client = config_entry.runtime_data.client

    @callback
    def async_add_binary_sensor(
        info: ZwaveDiscoveryInfo | NewZwaveDiscoveryInfo,
    ) -> None:
        """Add Z-Wave Binary Sensor."""
        driver = client.driver
        assert driver is not None  # Driver is ready before platforms are loaded.
        entities: list[Entity] = []

        if (
            isinstance(info, NewZwaveDiscoveryInfo)
            and info.entity_class is ZWaveNotificationBinarySensor
            and isinstance(
                info.entity_description, NotificationZWaveJSEntityDescription
            )
            and is_valid_notification_binary_sensor(info)
        ):
            entities.extend(
                ZWaveNotificationBinarySensor(
                    config_entry, driver, info, state_key, info.entity_description
                )
                for state_key in info.primary_value.metadata.states
                if int(state_key) not in info.entity_description.not_states
                and (
                    not info.entity_description.states
                    or int(state_key) in info.entity_description.states
                )
            )
        elif isinstance(info, NewZwaveDiscoveryInfo):
            pass  # other entity classes are not migrated yet
        elif info.platform_hint == "notification":
            # ensure the notification CC Value is valid as binary sensor
            if not is_valid_notification_binary_sensor(info):
                return
            if (
                notification_type := info.primary_value.metadata.cc_specific[
                    CC_SPECIFIC_NOTIFICATION_TYPE
                ]
            ) in MIGRATED_NOTIFICATION_TYPES:
                return
            # Get all sensors from Notification CC states
            for state_key in info.primary_value.metadata.states:
                if TYPE_CHECKING:
                    state_key = cast(str, state_key)
                # ignore idle key (0)
                if state_key == "0":
                    continue
                # get (optional) description for this state
                notification_description: (
                    NotificationZWaveJSEntityDescription | None
                ) = None
                for description in NOTIFICATION_SENSOR_MAPPINGS:
                    if (int(description.key) == notification_type) and (
                        not description.states or int(state_key) in description.states
                    ):
                        notification_description = description
                        break

                if (
                    notification_description
                    and int(state_key) in notification_description.not_states
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
        config_entry: ZwaveJSConfigEntry,
        driver: Driver,
        info: ZwaveDiscoveryInfo,
    ) -> None:
        """Initialize a ZWaveBooleanBinarySensor entity."""
        super().__init__(config_entry, driver, info)

        # Entity class attributes
        self._attr_name = self.generate_name(include_value_name=True)
        primary_value = self.info.primary_value
        if description := BOOLEAN_SENSOR_MAPPINGS.get(
            (primary_value.command_class, primary_value.property_)
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
        config_entry: ZwaveJSConfigEntry,
        driver: Driver,
        info: ZwaveDiscoveryInfo | NewZwaveDiscoveryInfo,
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
        config_entry: ZwaveJSConfigEntry,
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
        self, config_entry: ZwaveJSConfigEntry, driver: Driver, info: ZwaveDiscoveryInfo
    ) -> None:
        """Initialize a ZWaveConfigParameterBinarySensor entity."""
        super().__init__(config_entry, driver, info)

        property_key_name = self.info.primary_value.property_key_name
        # Entity class attributes
        self._attr_name = self.generate_name(
            alternate_value_name=self.info.primary_value.property_name,
            additional_info=[property_key_name] if property_key_name else None,
        )


DISCOVERY_SCHEMAS: list[NewZWaveDiscoverySchema] = [
    NewZWaveDiscoverySchema(
        platform=Platform.BINARY_SENSOR,
        primary_value=ZWaveValueDiscoverySchema(
            command_class={
                CommandClass.NOTIFICATION,
            },
            type={ValueType.NUMBER},
            any_available_states_keys={
                SmokeAlarmNotificationEvent.SENSOR_STATUS_SMOKE_DETECTED_LOCATION_PROVIDED,
                SmokeAlarmNotificationEvent.SENSOR_STATUS_SMOKE_DETECTED,
            },
            any_available_cc_specific={
                (CC_SPECIFIC_NOTIFICATION_TYPE, NotificationType.SMOKE_ALARM)
            },
        ),
        allow_multi=True,
        entity_description=NotificationZWaveJSEntityDescription(
            # NotificationType 1: Smoke Alarm - State Id's 1 and 2 - Smoke detected
            key=NOTIFICATION_SMOKE_ALARM,
            states={
                SmokeAlarmNotificationEvent.SENSOR_STATUS_SMOKE_DETECTED_LOCATION_PROVIDED,
                SmokeAlarmNotificationEvent.SENSOR_STATUS_SMOKE_DETECTED,
            },
            device_class=BinarySensorDeviceClass.SMOKE,
        ),
        entity_class=ZWaveNotificationBinarySensor,
    ),
    NewZWaveDiscoverySchema(
        platform=Platform.BINARY_SENSOR,
        primary_value=ZWaveValueDiscoverySchema(
            command_class={
                CommandClass.NOTIFICATION,
            },
            type={ValueType.NUMBER},
            any_available_states_keys={
                SmokeAlarmNotificationEvent.MAINTENANCE_STATUS_REPLACEMENT_REQUIRED,
                SmokeAlarmNotificationEvent.MAINTENANCE_STATUS_REPLACEMENT_REQUIRED_END_OF_LIFE,
                SmokeAlarmNotificationEvent.PERIODIC_INSPECTION_STATUS_MAINTENANCE_REQUIRED_PLANNED_PERIODIC_INSPECTION,
                SmokeAlarmNotificationEvent.DUST_IN_DEVICE_STATUS_MAINTENANCE_REQUIRED_DUST_IN_DEVICE,
            },
            any_available_cc_specific={
                (CC_SPECIFIC_NOTIFICATION_TYPE, NotificationType.SMOKE_ALARM)
            },
        ),
        allow_multi=True,
        entity_description=NotificationZWaveJSEntityDescription(
            # NotificationType 1: Smoke Alarm - State Id's 4, 5, 7, 8
            key=NOTIFICATION_SMOKE_ALARM,
            states={
                SmokeAlarmNotificationEvent.MAINTENANCE_STATUS_REPLACEMENT_REQUIRED,
                SmokeAlarmNotificationEvent.MAINTENANCE_STATUS_REPLACEMENT_REQUIRED_END_OF_LIFE,
                SmokeAlarmNotificationEvent.PERIODIC_INSPECTION_STATUS_MAINTENANCE_REQUIRED_PLANNED_PERIODIC_INSPECTION,
                SmokeAlarmNotificationEvent.DUST_IN_DEVICE_STATUS_MAINTENANCE_REQUIRED_DUST_IN_DEVICE,
            },
            device_class=BinarySensorDeviceClass.PROBLEM,
            entity_category=EntityCategory.DIAGNOSTIC,
        ),
        entity_class=ZWaveNotificationBinarySensor,
    ),
    NewZWaveDiscoverySchema(
        platform=Platform.BINARY_SENSOR,
        primary_value=ZWaveValueDiscoverySchema(
            command_class={
                CommandClass.NOTIFICATION,
            },
            type={ValueType.NUMBER},
            any_available_cc_specific={
                (CC_SPECIFIC_NOTIFICATION_TYPE, NotificationType.SMOKE_ALARM)
            },
        ),
        allow_multi=True,
        entity_description=NotificationZWaveJSEntityDescription(
            # NotificationType 1: Smoke Alarm - All other State Id's
            key=NOTIFICATION_SMOKE_ALARM,
            entity_category=EntityCategory.DIAGNOSTIC,
            not_states={
                SmokeAlarmNotificationEvent.SENSOR_STATUS_SMOKE_DETECTED_LOCATION_PROVIDED,
                SmokeAlarmNotificationEvent.SENSOR_STATUS_SMOKE_DETECTED,
                SmokeAlarmNotificationEvent.MAINTENANCE_STATUS_REPLACEMENT_REQUIRED,
                SmokeAlarmNotificationEvent.MAINTENANCE_STATUS_REPLACEMENT_REQUIRED_END_OF_LIFE,
                SmokeAlarmNotificationEvent.PERIODIC_INSPECTION_STATUS_MAINTENANCE_REQUIRED_PLANNED_PERIODIC_INSPECTION,
                SmokeAlarmNotificationEvent.DUST_IN_DEVICE_STATUS_MAINTENANCE_REQUIRED_DUST_IN_DEVICE,
            },
        ),
        entity_class=ZWaveNotificationBinarySensor,
    ),
]
