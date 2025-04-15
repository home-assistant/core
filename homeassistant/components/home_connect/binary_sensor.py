"""Provides a binary sensor for Home Connect."""

from dataclasses import dataclass
from typing import cast

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
from .const import REFRIGERATION_STATUS_DOOR_CLOSED, REFRIGERATION_STATUS_DOOR_OPEN
from .coordinator import HomeConnectApplianceData, HomeConnectConfigEntry
from .entity import HomeConnectEntity

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


def _get_entities_for_appliance(
    entry: HomeConnectConfigEntry,
    appliance: HomeConnectApplianceData,
) -> list[HomeConnectEntity]:
    """Get a list of entities."""
    entities: list[HomeConnectEntity] = [
        HomeConnectConnectivityBinarySensor(
            entry.runtime_data, appliance, CONNECTED_BINARY_ENTITY_DESCRIPTION
        )
    ]
    entities.extend(
        HomeConnectBinarySensor(entry.runtime_data, appliance, description)
        for description in BINARY_SENSORS
        if description.key in appliance.status
    )
    return entities


async def async_setup_entry(
    hass: HomeAssistant,
    entry: HomeConnectConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the Home Connect binary sensor."""
    setup_home_connect_entry(
        entry,
        _get_entities_for_appliance,
        async_add_entities,
    )


class HomeConnectBinarySensor(HomeConnectEntity, BinarySensorEntity):
    """Binary sensor for Home Connect."""

    entity_description: HomeConnectBinarySensorEntityDescription

    def update_native_value(self) -> None:
        """Set the native value of the binary sensor."""
        status = self.appliance.status[cast(StatusKey, self.bsh_key)].value
        if isinstance(status, bool):
            self._attr_is_on = status
        elif self.entity_description.boolean_map:
            self._attr_is_on = self.entity_description.boolean_map.get(status)
        else:
            self._attr_is_on = None


class HomeConnectConnectivityBinarySensor(HomeConnectEntity, BinarySensorEntity):
    """Binary sensor for Home Connect appliance's connection status."""

    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def update_native_value(self) -> None:
        """Set the native value of the binary sensor."""
        self._attr_is_on = self.appliance.info.connected

    @property
    def available(self) -> bool:
        """Return the availability."""
        return self.coordinator.last_update_success
