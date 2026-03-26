"""Representation of Z-Wave binary sensors."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from enum import IntEnum
from typing import TYPE_CHECKING, cast

from zwave_js_server.const import CommandClass
from zwave_js_server.const.command_class.lock import DOOR_STATUS_PROPERTY
from zwave_js_server.const.command_class.notification import (
    CC_SPECIFIC_NOTIFICATION_TYPE,
    AccessControlNotificationEvent,
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
from .helpers import (
    get_opening_state_notification_value,
    is_opening_state_notification_value,
)
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

# Deprecated/legacy synthetic Access Control door state notification
# event IDs that don't exist in zwave-js-server
ACCESS_CONTROL_DOOR_STATE_OPEN_REGULAR = 5632
ACCESS_CONTROL_DOOR_STATE_OPEN_TILT = 5633


# Numeric State values used by the "Opening state" notification variable.
# This is only needed temporarily until the legacy Access Control door state binary sensors are removed.
class OpeningState(IntEnum):
    """Opening state values exposed by Access Control notifications."""

    CLOSED = 0
    OPEN = 1
    TILTED = 2


# parse_opening_state helpers for the DEPRECATED legacy Access Control binary sensors.
def _legacy_is_closed(opening_state: OpeningState) -> bool:
    """Return if Opening state represents closed."""
    return opening_state is OpeningState.CLOSED


def _legacy_is_open(opening_state: OpeningState) -> bool:
    """Return if Opening state represents open."""
    return opening_state is OpeningState.OPEN


def _legacy_is_open_or_tilted(opening_state: OpeningState) -> bool:
    """Return if Opening state represents open or tilted."""
    return opening_state in (OpeningState.OPEN, OpeningState.TILTED)


def _legacy_is_tilted(opening_state: OpeningState) -> bool:
    """Return if Opening state represents tilted."""
    return opening_state is OpeningState.TILTED


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


@dataclass(frozen=True, kw_only=True)
class OpeningStateZWaveJSEntityDescription(BinarySensorEntityDescription):
    """Describe a legacy Access Control binary sensor that derives state from Opening state."""

    state_key: int
    parse_opening_state: Callable[[OpeningState], bool]


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
    NotificationType.ACCESS_CONTROL,
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
    # Access Control - Opening state is exposed as a single enum sensor instead
    # of fanning out one binary sensor per state.
    if is_opening_state_notification_value(info.primary_value):
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
                ZWaveNotificationBinarySensor(config_entry, driver, info, state_key)
                for state_key in info.primary_value.metadata.states
                if int(state_key) not in info.entity_description.not_states
                and (
                    not info.entity_description.states
                    or int(state_key) in info.entity_description.states
                )
            )
        elif (
            isinstance(info, NewZwaveDiscoveryInfo)
            and info.entity_class is ZWaveBooleanBinarySensor
        ):
            entities.append(ZWaveBooleanBinarySensor(config_entry, driver, info))
        elif (
            isinstance(info, NewZwaveDiscoveryInfo)
            and info.entity_class is ZWaveLegacyDoorStateBinarySensor
        ):
            entities.append(
                ZWaveLegacyDoorStateBinarySensor(config_entry, driver, info)
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
        info: ZwaveDiscoveryInfo | NewZwaveDiscoveryInfo,
    ) -> None:
        """Initialize a ZWaveBooleanBinarySensor entity."""
        super().__init__(config_entry, driver, info)

        if isinstance(info, NewZwaveDiscoveryInfo):
            # Entity name and description are set from the discovery schema.
            return

        # Entity class attributes for old-style discovery.
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


class ZWaveLegacyDoorStateBinarySensor(ZWaveBaseEntity, BinarySensorEntity):
    """DEPRECATED: Legacy door state binary sensors.

    These entities exist purely for backwards compatibility with users who had
    door state binary sensors before the Opening state value was introduced.
    They are disabled by default when the Opening state value is present and
    should not be extended. State is derived from the Opening state notification
    value using the parse_opening_state function defined on the entity description.
    """

    entity_description: OpeningStateZWaveJSEntityDescription

    def __init__(
        self,
        config_entry: ZwaveJSConfigEntry,
        driver: Driver,
        info: NewZwaveDiscoveryInfo,
    ) -> None:
        """Initialize a legacy Door state binary sensor entity."""
        super().__init__(config_entry, driver, info)
        opening_state_value = get_opening_state_notification_value(
            self.info.node, self.info.primary_value.endpoint
        )
        assert opening_state_value is not None  # guaranteed by required_values schema
        self._opening_state_value_id = opening_state_value.value_id
        self.watched_value_ids.add(opening_state_value.value_id)
        self._attr_unique_id = (
            f"{self._attr_unique_id}.{self.entity_description.state_key}"
        )

    @property
    def is_on(self) -> bool | None:
        """Return if the sensor is on or off."""
        value = self.info.node.values.get(self._opening_state_value_id)
        if value is None:
            return None
        opening_state = value.value
        if opening_state is None:
            return None
        try:
            return self.entity_description.parse_opening_state(
                OpeningState(int(opening_state))
            )
        except TypeError, ValueError:
            return None


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


OPENING_STATE_NOTIFICATION_SCHEMA = ZWaveValueDiscoverySchema(
    command_class={CommandClass.NOTIFICATION},
    property={"Access Control"},
    property_key={"Opening state"},
    type={ValueType.NUMBER},
    any_available_cc_specific={
        (CC_SPECIFIC_NOTIFICATION_TYPE, NotificationType.ACCESS_CONTROL)
    },
)


DISCOVERY_SCHEMAS: list[NewZWaveDiscoverySchema] = [
    NewZWaveDiscoverySchema(
        platform=Platform.BINARY_SENSOR,
        primary_value=ZWaveValueDiscoverySchema(
            command_class={CommandClass.NOTIFICATION},
            property={"Access Control"},
            property_key={"Lock state"},
            type={ValueType.NUMBER},
            any_available_states_keys={1, 2, 3, 4},
            any_available_cc_specific={
                (CC_SPECIFIC_NOTIFICATION_TYPE, NotificationType.ACCESS_CONTROL)
            },
        ),
        allow_multi=True,
        entity_description=NotificationZWaveJSEntityDescription(
            # NotificationType 6: Access Control - State Id's 1, 2, 3, 4 (Lock)
            key=NOTIFICATION_ACCESS_CONTROL,
            states={1, 2, 3, 4},
            device_class=BinarySensorDeviceClass.LOCK,
        ),
        entity_class=ZWaveNotificationBinarySensor,
    ),
    NewZWaveDiscoverySchema(
        platform=Platform.BINARY_SENSOR,
        primary_value=ZWaveValueDiscoverySchema(
            command_class={CommandClass.NOTIFICATION},
            property={"Access Control"},
            property_key={"Lock state"},
            type={ValueType.NUMBER},
            any_available_states_keys={11},
            any_available_cc_specific={
                (CC_SPECIFIC_NOTIFICATION_TYPE, NotificationType.ACCESS_CONTROL)
            },
        ),
        entity_description=NotificationZWaveJSEntityDescription(
            # NotificationType 6: Access Control - State Id's 11 (Lock jammed)
            key=NOTIFICATION_ACCESS_CONTROL,
            states={11},
            device_class=BinarySensorDeviceClass.PROBLEM,
            entity_category=EntityCategory.DIAGNOSTIC,
        ),
        entity_class=ZWaveNotificationBinarySensor,
    ),
    # -------------------------------------------------------------------
    # DEPRECATED legacy Access Control door/window binary sensors.
    # These schemas exist only for backwards compatibility with users who
    # already have these entities registered. New integrations should use
    # the Opening state enum sensor instead. Do not add new schemas here.
    # All schemas below use ZWaveLegacyDoorStateBinarySensor and are
    # disabled by default (entity_registry_enabled_default=False).
    # -------------------------------------------------------------------
    NewZWaveDiscoverySchema(
        platform=Platform.BINARY_SENSOR,
        primary_value=ZWaveValueDiscoverySchema(
            command_class={CommandClass.NOTIFICATION},
            property={"Access Control"},
            property_key={"Door state (simple)"},
            type={ValueType.NUMBER},
            any_available_states_keys={
                AccessControlNotificationEvent.DOOR_STATE_WINDOW_DOOR_IS_OPEN
            },
            any_available_cc_specific={
                (CC_SPECIFIC_NOTIFICATION_TYPE, NotificationType.ACCESS_CONTROL)
            },
        ),
        required_values=[OPENING_STATE_NOTIFICATION_SCHEMA],
        allow_multi=True,
        entity_description=OpeningStateZWaveJSEntityDescription(
            key="legacy_access_control_door_state_simple_open",
            name="Window/door is open",
            state_key=AccessControlNotificationEvent.DOOR_STATE_WINDOW_DOOR_IS_OPEN,
            parse_opening_state=_legacy_is_open_or_tilted,
            device_class=BinarySensorDeviceClass.DOOR,
            entity_registry_enabled_default=False,
        ),
        entity_class=ZWaveLegacyDoorStateBinarySensor,
    ),
    NewZWaveDiscoverySchema(
        platform=Platform.BINARY_SENSOR,
        primary_value=ZWaveValueDiscoverySchema(
            command_class={CommandClass.NOTIFICATION},
            property={"Access Control"},
            property_key={"Door state (simple)"},
            type={ValueType.NUMBER},
            any_available_states_keys={
                AccessControlNotificationEvent.DOOR_STATE_WINDOW_DOOR_IS_CLOSED
            },
            any_available_cc_specific={
                (CC_SPECIFIC_NOTIFICATION_TYPE, NotificationType.ACCESS_CONTROL)
            },
        ),
        required_values=[OPENING_STATE_NOTIFICATION_SCHEMA],
        allow_multi=True,
        entity_description=OpeningStateZWaveJSEntityDescription(
            key="legacy_access_control_door_state_simple_closed",
            name="Window/door is closed",
            state_key=AccessControlNotificationEvent.DOOR_STATE_WINDOW_DOOR_IS_CLOSED,
            parse_opening_state=_legacy_is_closed,
            entity_registry_enabled_default=False,
        ),
        entity_class=ZWaveLegacyDoorStateBinarySensor,
    ),
    NewZWaveDiscoverySchema(
        platform=Platform.BINARY_SENSOR,
        primary_value=ZWaveValueDiscoverySchema(
            command_class={CommandClass.NOTIFICATION},
            property={"Access Control"},
            property_key={"Door state"},
            type={ValueType.NUMBER},
            any_available_states_keys={
                AccessControlNotificationEvent.DOOR_STATE_WINDOW_DOOR_IS_OPEN
            },
            any_available_cc_specific={
                (CC_SPECIFIC_NOTIFICATION_TYPE, NotificationType.ACCESS_CONTROL)
            },
        ),
        required_values=[OPENING_STATE_NOTIFICATION_SCHEMA],
        allow_multi=True,
        entity_description=OpeningStateZWaveJSEntityDescription(
            key="legacy_access_control_door_state_open",
            name="Window/door is open",
            state_key=AccessControlNotificationEvent.DOOR_STATE_WINDOW_DOOR_IS_OPEN,
            parse_opening_state=_legacy_is_open,
            device_class=BinarySensorDeviceClass.DOOR,
            entity_registry_enabled_default=False,
        ),
        entity_class=ZWaveLegacyDoorStateBinarySensor,
    ),
    NewZWaveDiscoverySchema(
        platform=Platform.BINARY_SENSOR,
        primary_value=ZWaveValueDiscoverySchema(
            command_class={CommandClass.NOTIFICATION},
            property={"Access Control"},
            property_key={"Door state"},
            type={ValueType.NUMBER},
            any_available_states_keys={
                AccessControlNotificationEvent.DOOR_STATE_WINDOW_DOOR_IS_CLOSED
            },
            any_available_cc_specific={
                (CC_SPECIFIC_NOTIFICATION_TYPE, NotificationType.ACCESS_CONTROL)
            },
        ),
        required_values=[OPENING_STATE_NOTIFICATION_SCHEMA],
        allow_multi=True,
        entity_description=OpeningStateZWaveJSEntityDescription(
            key="legacy_access_control_door_state_closed",
            name="Window/door is closed",
            state_key=AccessControlNotificationEvent.DOOR_STATE_WINDOW_DOOR_IS_CLOSED,
            parse_opening_state=_legacy_is_closed,
            entity_registry_enabled_default=False,
        ),
        entity_class=ZWaveLegacyDoorStateBinarySensor,
    ),
    NewZWaveDiscoverySchema(
        platform=Platform.BINARY_SENSOR,
        primary_value=ZWaveValueDiscoverySchema(
            command_class={CommandClass.NOTIFICATION},
            property={"Access Control"},
            property_key={"Door state"},
            type={ValueType.NUMBER},
            any_available_states_keys={ACCESS_CONTROL_DOOR_STATE_OPEN_REGULAR},
            any_available_cc_specific={
                (CC_SPECIFIC_NOTIFICATION_TYPE, NotificationType.ACCESS_CONTROL)
            },
        ),
        required_values=[OPENING_STATE_NOTIFICATION_SCHEMA],
        allow_multi=True,
        entity_description=OpeningStateZWaveJSEntityDescription(
            key="legacy_access_control_door_state_open_regular",
            name="Window/door is open in regular position",
            state_key=ACCESS_CONTROL_DOOR_STATE_OPEN_REGULAR,
            parse_opening_state=_legacy_is_open,
            entity_registry_enabled_default=False,
        ),
        entity_class=ZWaveLegacyDoorStateBinarySensor,
    ),
    NewZWaveDiscoverySchema(
        platform=Platform.BINARY_SENSOR,
        primary_value=ZWaveValueDiscoverySchema(
            command_class={CommandClass.NOTIFICATION},
            property={"Access Control"},
            property_key={"Door state"},
            type={ValueType.NUMBER},
            any_available_states_keys={ACCESS_CONTROL_DOOR_STATE_OPEN_TILT},
            any_available_cc_specific={
                (CC_SPECIFIC_NOTIFICATION_TYPE, NotificationType.ACCESS_CONTROL)
            },
        ),
        required_values=[OPENING_STATE_NOTIFICATION_SCHEMA],
        allow_multi=True,
        entity_description=OpeningStateZWaveJSEntityDescription(
            key="legacy_access_control_door_state_open_tilt",
            name="Window/door is open in tilt position",
            state_key=ACCESS_CONTROL_DOOR_STATE_OPEN_TILT,
            parse_opening_state=_legacy_is_tilted,
            entity_registry_enabled_default=False,
        ),
        entity_class=ZWaveLegacyDoorStateBinarySensor,
    ),
    NewZWaveDiscoverySchema(
        platform=Platform.BINARY_SENSOR,
        primary_value=ZWaveValueDiscoverySchema(
            command_class={CommandClass.NOTIFICATION},
            property={"Access Control"},
            property_key={"Door tilt state"},
            type={ValueType.NUMBER},
            any_available_states_keys={OpeningState.OPEN},
            any_available_cc_specific={
                (CC_SPECIFIC_NOTIFICATION_TYPE, NotificationType.ACCESS_CONTROL)
            },
        ),
        required_values=[OPENING_STATE_NOTIFICATION_SCHEMA],
        allow_multi=True,
        entity_description=OpeningStateZWaveJSEntityDescription(
            key="legacy_access_control_door_tilt_state_tilted",
            name="Window/door is tilted",
            state_key=OpeningState.OPEN,
            parse_opening_state=_legacy_is_tilted,
            entity_registry_enabled_default=False,
        ),
        entity_class=ZWaveLegacyDoorStateBinarySensor,
    ),
    # -------------------------------------------------------------------
    # Access Control door/window binary sensors for devices that do NOT have the
    # new "Opening state" notification value. These replace the old-style discovery
    # that used NOTIFICATION_SENSOR_MAPPINGS.
    #
    # Each property_key uses two schemas so that only the "open" state entity gets
    # device_class=DOOR, while the other state entities (e.g. "closed") do not.
    # The first schema uses allow_multi=True so it does not consume the value, allowing
    # the second schema to also match and create entities for the remaining states.
    NewZWaveDiscoverySchema(
        platform=Platform.BINARY_SENSOR,
        primary_value=ZWaveValueDiscoverySchema(
            command_class={CommandClass.NOTIFICATION},
            property={"Access Control"},
            property_key={"Door state (simple)"},
            type={ValueType.NUMBER},
            any_available_states_keys={
                AccessControlNotificationEvent.DOOR_STATE_WINDOW_DOOR_IS_OPEN
            },
            any_available_cc_specific={
                (CC_SPECIFIC_NOTIFICATION_TYPE, NotificationType.ACCESS_CONTROL)
            },
        ),
        absent_values=[OPENING_STATE_NOTIFICATION_SCHEMA],
        allow_multi=True,
        entity_description=NotificationZWaveJSEntityDescription(
            key=NOTIFICATION_ACCESS_CONTROL,
            states={AccessControlNotificationEvent.DOOR_STATE_WINDOW_DOOR_IS_OPEN},
            device_class=BinarySensorDeviceClass.DOOR,
        ),
        entity_class=ZWaveNotificationBinarySensor,
    ),
    NewZWaveDiscoverySchema(
        platform=Platform.BINARY_SENSOR,
        primary_value=ZWaveValueDiscoverySchema(
            command_class={CommandClass.NOTIFICATION},
            property={"Access Control"},
            property_key={"Door state (simple)"},
            type={ValueType.NUMBER},
            any_available_states_keys={
                AccessControlNotificationEvent.DOOR_STATE_WINDOW_DOOR_IS_OPEN
            },
            any_available_cc_specific={
                (CC_SPECIFIC_NOTIFICATION_TYPE, NotificationType.ACCESS_CONTROL)
            },
        ),
        absent_values=[OPENING_STATE_NOTIFICATION_SCHEMA],
        entity_description=NotificationZWaveJSEntityDescription(
            key=NOTIFICATION_ACCESS_CONTROL,
            not_states={AccessControlNotificationEvent.DOOR_STATE_WINDOW_DOOR_IS_OPEN},
        ),
        entity_class=ZWaveNotificationBinarySensor,
    ),
    NewZWaveDiscoverySchema(
        platform=Platform.BINARY_SENSOR,
        primary_value=ZWaveValueDiscoverySchema(
            command_class={CommandClass.NOTIFICATION},
            property={"Access Control"},
            property_key={"Door state"},
            type={ValueType.NUMBER},
            any_available_states_keys={
                AccessControlNotificationEvent.DOOR_STATE_WINDOW_DOOR_IS_OPEN
            },
            any_available_cc_specific={
                (CC_SPECIFIC_NOTIFICATION_TYPE, NotificationType.ACCESS_CONTROL)
            },
        ),
        absent_values=[OPENING_STATE_NOTIFICATION_SCHEMA],
        allow_multi=True,
        entity_description=NotificationZWaveJSEntityDescription(
            key=NOTIFICATION_ACCESS_CONTROL,
            states={AccessControlNotificationEvent.DOOR_STATE_WINDOW_DOOR_IS_OPEN},
            device_class=BinarySensorDeviceClass.DOOR,
        ),
        entity_class=ZWaveNotificationBinarySensor,
    ),
    NewZWaveDiscoverySchema(
        platform=Platform.BINARY_SENSOR,
        primary_value=ZWaveValueDiscoverySchema(
            command_class={CommandClass.NOTIFICATION},
            property={"Access Control"},
            property_key={"Door state"},
            type={ValueType.NUMBER},
            any_available_states_keys={
                AccessControlNotificationEvent.DOOR_STATE_WINDOW_DOOR_IS_OPEN
            },
            any_available_cc_specific={
                (CC_SPECIFIC_NOTIFICATION_TYPE, NotificationType.ACCESS_CONTROL)
            },
        ),
        absent_values=[OPENING_STATE_NOTIFICATION_SCHEMA],
        entity_description=NotificationZWaveJSEntityDescription(
            key=NOTIFICATION_ACCESS_CONTROL,
            not_states={AccessControlNotificationEvent.DOOR_STATE_WINDOW_DOOR_IS_OPEN},
        ),
        entity_class=ZWaveNotificationBinarySensor,
    ),
    NewZWaveDiscoverySchema(
        platform=Platform.BINARY_SENSOR,
        primary_value=ZWaveValueDiscoverySchema(
            command_class={CommandClass.NOTIFICATION},
            property={"Access Control"},
            property_key={"Door tilt state"},
            type={ValueType.NUMBER},
            any_available_states_keys={OpeningState.OPEN},
            any_available_cc_specific={
                (CC_SPECIFIC_NOTIFICATION_TYPE, NotificationType.ACCESS_CONTROL)
            },
        ),
        absent_values=[OPENING_STATE_NOTIFICATION_SCHEMA],
        entity_description=NotificationZWaveJSEntityDescription(
            key=NOTIFICATION_ACCESS_CONTROL,
            states={OpeningState.OPEN},
        ),
        entity_class=ZWaveNotificationBinarySensor,
    ),
    NewZWaveDiscoverySchema(
        platform=Platform.BINARY_SENSOR,
        primary_value=ZWaveValueDiscoverySchema(
            command_class={CommandClass.NOTIFICATION},
            property={"Access Control"},
            type={ValueType.NUMBER},
            any_available_cc_specific={
                (CC_SPECIFIC_NOTIFICATION_TYPE, NotificationType.ACCESS_CONTROL)
            },
        ),
        allow_multi=True,
        entity_description=NotificationZWaveJSEntityDescription(
            # NotificationType 6: Access Control - All other notification values.
            # not_states excludes states already handled by more specific schemas above,
            # so this catch-all only fires for genuinely unhandled property keys
            # (e.g. barrier, keypad, credential events).
            key=NOTIFICATION_ACCESS_CONTROL,
            entity_category=EntityCategory.DIAGNOSTIC,
            not_states={
                0,
                # Lock state values (Lock state schemas consume the value when state 11 is
                # available, but may not when state 11 is absent)
                1,
                2,
                3,
                4,
                11,
                # Door state (simple) / Door state values
                AccessControlNotificationEvent.DOOR_STATE_WINDOW_DOOR_IS_OPEN,
                AccessControlNotificationEvent.DOOR_STATE_WINDOW_DOOR_IS_CLOSED,
                ACCESS_CONTROL_DOOR_STATE_OPEN_REGULAR,
                ACCESS_CONTROL_DOOR_STATE_OPEN_TILT,
            },
        ),
        entity_class=ZWaveNotificationBinarySensor,
    ),
    # -------------------------------------------------------------------
    NewZWaveDiscoverySchema(
        # Hoppe eHandle ConnectSense (0x0313:0x0701:0x0002) - window tilt sensor.
        # The window tilt state is exposed as a binary sensor that is disabled by default
        # instead of a notification sensor. We enable that sensor and give it a name
        # that is more consistent with the other window related entities.
        platform=Platform.BINARY_SENSOR,
        manufacturer_id={0x0313},
        product_id={0x0002},
        product_type={0x0701},
        primary_value=ZWaveValueDiscoverySchema(
            command_class={CommandClass.SENSOR_BINARY},
            property={"Tilt"},
            type={ValueType.BOOLEAN},
        ),
        entity_description=BinarySensorEntityDescription(
            key="window_door_is_tilted",
            name="Window/door is tilted",
            device_class=BinarySensorDeviceClass.WINDOW,
        ),
        entity_class=ZWaveBooleanBinarySensor,
    ),
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
                0,
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
