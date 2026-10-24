"""Provides a binary sensor for Home Connect."""

from dataclasses import dataclass
from typing import cast, override

from aiohomeconnect.model import EventKey, StatusKey

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .common import setup_home_connect_entry
from .const import (
    APPLIANCES_WITH_PROGRAM_TIMES,
    REFRIGERATION_STATUS_DOOR_CLOSED,
    REFRIGERATION_STATUS_DOOR_OPEN,
)
from .coordinator import HomeConnectApplianceCoordinator, HomeConnectConfigEntry
from .entity import HomeConnectEntity, is_program_running

PARALLEL_UPDATES = 0

REFRIGERATION_DOOR_BOOLEAN_MAP = {
    REFRIGERATION_STATUS_DOOR_CLOSED: False,
    REFRIGERATION_STATUS_DOOR_OPEN: True,
}


@dataclass(frozen=True, kw_only=True)
class HomeConnectBinarySensorEntityDescription(BinarySensorEntityDescription):
    """Entity Description class for binary sensors."""

    boolean_map: dict[str, bool] | None = None


BINARY_SENSORS = (
    HomeConnectBinarySensorEntityDescription(
        key=StatusKey.BSH_COMMON_REMOTE_CONTROL_ACTIVE,
        translation_key="remote_control",
    ),
    HomeConnectBinarySensorEntityDescription(
        key=StatusKey.BSH_COMMON_REMOTE_CONTROL_START_ALLOWED,
        translation_key="remote_start",
    ),
    HomeConnectBinarySensorEntityDescription(
        key=StatusKey.BSH_COMMON_LOCAL_CONTROL_ACTIVE,
        translation_key="local_control",
    ),
    HomeConnectBinarySensorEntityDescription(
        key=StatusKey.BSH_COMMON_BATTERY_CHARGING_STATE,
        device_class=BinarySensorDeviceClass.BATTERY_CHARGING,
        boolean_map={
            "BSH.Common.EnumType.BatteryChargingState.Charging": True,
            "BSH.Common.EnumType.BatteryChargingState.Discharging": False,
        },
        translation_key="battery_charging_state",
    ),
    HomeConnectBinarySensorEntityDescription(
        key=StatusKey.BSH_COMMON_CHARGING_CONNECTION,
        device_class=BinarySensorDeviceClass.PLUG,
        boolean_map={
            "BSH.Common.EnumType.ChargingConnection.Connected": True,
            "BSH.Common.EnumType.ChargingConnection.Disconnected": False,
        },
        translation_key="charging_connection",
    ),
    HomeConnectBinarySensorEntityDescription(
        key=StatusKey.BSH_COMMON_INTERIOR_ILLUMINATION_ACTIVE,
        translation_key="interior_illumination_active",
        device_class=BinarySensorDeviceClass.LIGHT,
    ),
    HomeConnectBinarySensorEntityDescription(
        key=StatusKey.CONSUMER_PRODUCTS_CLEANING_ROBOT_DUST_BOX_INSERTED,
        translation_key="dust_box_inserted",
    ),
    HomeConnectBinarySensorEntityDescription(
        key=StatusKey.CONSUMER_PRODUCTS_CLEANING_ROBOT_LIFTED,
        translation_key="lifted",
    ),
    HomeConnectBinarySensorEntityDescription(
        key=StatusKey.CONSUMER_PRODUCTS_CLEANING_ROBOT_LOST,
        translation_key="lost",
    ),
    HomeConnectBinarySensorEntityDescription(
        key=StatusKey.REFRIGERATION_COMMON_DOOR_BOTTLE_COOLER,
        boolean_map=REFRIGERATION_DOOR_BOOLEAN_MAP,
        device_class=BinarySensorDeviceClass.DOOR,
        translation_key="bottle_cooler_door",
    ),
    HomeConnectBinarySensorEntityDescription(
        key=StatusKey.REFRIGERATION_COMMON_DOOR_CHILLER_COMMON,
        boolean_map=REFRIGERATION_DOOR_BOOLEAN_MAP,
        device_class=BinarySensorDeviceClass.DOOR,
        translation_key="common_chiller_door",
    ),
    HomeConnectBinarySensorEntityDescription(
        key=StatusKey.REFRIGERATION_COMMON_DOOR_CHILLER,
        boolean_map=REFRIGERATION_DOOR_BOOLEAN_MAP,
        device_class=BinarySensorDeviceClass.DOOR,
        translation_key="chiller_door",
    ),
    HomeConnectBinarySensorEntityDescription(
        key=StatusKey.REFRIGERATION_COMMON_DOOR_CHILLER_LEFT,
        boolean_map=REFRIGERATION_DOOR_BOOLEAN_MAP,
        device_class=BinarySensorDeviceClass.DOOR,
        translation_key="left_chiller_door",
    ),
    HomeConnectBinarySensorEntityDescription(
        key=StatusKey.REFRIGERATION_COMMON_DOOR_CHILLER_RIGHT,
        boolean_map=REFRIGERATION_DOOR_BOOLEAN_MAP,
        device_class=BinarySensorDeviceClass.DOOR,
        translation_key="right_chiller_door",
    ),
    HomeConnectBinarySensorEntityDescription(
        key=StatusKey.REFRIGERATION_COMMON_DOOR_FLEX_COMPARTMENT,
        boolean_map=REFRIGERATION_DOOR_BOOLEAN_MAP,
        device_class=BinarySensorDeviceClass.DOOR,
        translation_key="flex_compartment_door",
    ),
    HomeConnectBinarySensorEntityDescription(
        key=StatusKey.REFRIGERATION_COMMON_DOOR_FREEZER,
        boolean_map=REFRIGERATION_DOOR_BOOLEAN_MAP,
        device_class=BinarySensorDeviceClass.DOOR,
        translation_key="freezer_door",
    ),
    HomeConnectBinarySensorEntityDescription(
        key=StatusKey.REFRIGERATION_COMMON_DOOR_REFRIGERATOR,
        boolean_map=REFRIGERATION_DOOR_BOOLEAN_MAP,
        device_class=BinarySensorDeviceClass.DOOR,
        translation_key="refrigerator_door",
    ),
    HomeConnectBinarySensorEntityDescription(
        key=StatusKey.REFRIGERATION_COMMON_DOOR_WINE_COMPARTMENT,
        boolean_map=REFRIGERATION_DOOR_BOOLEAN_MAP,
        device_class=BinarySensorDeviceClass.DOOR,
        translation_key="wine_compartment_door",
    ),
)

CONNECTED_BINARY_ENTITY_DESCRIPTION = BinarySensorEntityDescription(
    key=EventKey.BSH_COMMON_APPLIANCE_CONNECTED,
    device_class=BinarySensorDeviceClass.CONNECTIVITY,
)

REMAINING_PROGRAM_TIME_SET_ENTITY_DESCRIPTION = BinarySensorEntityDescription(
    key=EventKey.BSH_COMMON_OPTION_REMAINING_PROGRAM_TIME,
    translation_key="remaining_program_time_set",
)


def _get_entities_for_appliance(
    appliance_coordinator: HomeConnectApplianceCoordinator,
) -> list[HomeConnectEntity]:
    """Get a list of entities."""
    entities: list[HomeConnectEntity] = [
        HomeConnectConnectivityBinarySensor(
            appliance_coordinator, CONNECTED_BINARY_ENTITY_DESCRIPTION
        )
    ]
    entities.extend(
        HomeConnectBinarySensor(appliance_coordinator, description)
        for description in BINARY_SENSORS
        if description.key in appliance_coordinator.data.status
    )
    if appliance_coordinator.data.info.type in APPLIANCES_WITH_PROGRAM_TIMES:
        entities.append(
            HomeConnectRemainingProgramTimeSetBinarySensor(
                appliance_coordinator, REMAINING_PROGRAM_TIME_SET_ENTITY_DESCRIPTION
            )
        )
    return entities


async def async_setup_entry(
    hass: HomeAssistant,
    entry: HomeConnectConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the Home Connect binary sensor."""
    setup_home_connect_entry(
        hass,
        entry,
        _get_entities_for_appliance,
        async_add_entities,
    )


class HomeConnectBinarySensor(HomeConnectEntity, BinarySensorEntity):
    """Binary sensor for Home Connect."""

    entity_description: HomeConnectBinarySensorEntityDescription

    @override
    def update_native_value(self) -> None:
        """Set the native value of the binary sensor."""
        status = self.appliance.status[cast(StatusKey, self.bsh_key)].value
        if isinstance(status, bool):
            self._attr_is_on = status
        elif self.entity_description.boolean_map:
            self._attr_is_on = self.entity_description.boolean_map.get(status)
        else:
            self._attr_is_on = None


class HomeConnectRemainingProgramTimeSetBinarySensor(
    HomeConnectEntity, BinarySensorEntity
):
    """Binary sensor for whether the current program reports a remaining time."""

    @override
    async def async_added_to_hass(self) -> None:
        """Register listener."""
        await super().async_added_to_hass()
        self.async_on_remove(
            self.coordinator.async_add_listener(
                self._handle_coordinator_update,
                EventKey.BSH_COMMON_STATUS_OPERATION_STATE,
            )
        )

    @property
    @override
    def available(self) -> bool:
        """Return true if a program is running, paused or finished."""
        return super().available and is_program_running(self.appliance)

    @override
    def update_native_value(self) -> None:
        """Set the native value of the binary sensor."""
        event = self.appliance.events.get(
            EventKey.BSH_COMMON_OPTION_REMAINING_PROGRAM_TIME
        )
        self._attr_is_on = (
            event is not None
            and isinstance(event.value, int | float)
            and event.value > 0
        )


class HomeConnectConnectivityBinarySensor(HomeConnectEntity, BinarySensorEntity):
    """Binary sensor for Home Connect appliance's connection status."""

    _attr_entity_category = EntityCategory.DIAGNOSTIC

    @override
    def update_native_value(self) -> None:
        """Set the native value of the binary sensor."""
        self._attr_is_on = self.appliance.info.connected

    @property
    @override
    def available(self) -> bool:
        """Return the availability."""
        return self.coordinator.last_update_success
