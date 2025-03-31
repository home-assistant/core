"""Provides a binary sensor for Home Connect."""

from dataclasses import dataclass
from typing import cast

from aiohomeconnect.model import EventKey, StatusKey

from homeassistant.components.automation import automations_with_entity
from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.components.script import scripts_with_entity
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.issue_registry import (
    IssueSeverity,
    async_create_issue,
    async_delete_issue,
)

from .common import setup_home_connect_entry
from .const import (
    BSH_DOOR_STATE_CLOSED,
    BSH_DOOR_STATE_LOCKED,
    BSH_DOOR_STATE_OPEN,
    DOMAIN,
    REFRIGERATION_STATUS_DOOR_CLOSED,
    REFRIGERATION_STATUS_DOOR_OPEN,
)
from .coordinator import (
    HomeConnectApplianceData,
    HomeConnectConfigEntry,
    HomeConnectCoordinator,
)
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
    if StatusKey.BSH_COMMON_DOOR_STATE in appliance.status:
        entities.append(HomeConnectDoorBinarySensor(entry.runtime_data, appliance))
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


class HomeConnectDoorBinarySensor(HomeConnectBinarySensor):
    """Binary sensor for Home Connect Generic Door."""

    _attr_has_entity_name = False

    def __init__(
        self,
        coordinator: HomeConnectCoordinator,
        appliance: HomeConnectApplianceData,
    ) -> None:
        """Initialize the entity."""
        super().__init__(
            coordinator,
            appliance,
            HomeConnectBinarySensorEntityDescription(
                key=StatusKey.BSH_COMMON_DOOR_STATE,
                device_class=BinarySensorDeviceClass.DOOR,
                boolean_map={
                    BSH_DOOR_STATE_CLOSED: False,
                    BSH_DOOR_STATE_LOCKED: False,
                    BSH_DOOR_STATE_OPEN: True,
                },
                entity_registry_enabled_default=False,
            ),
        )
        self._attr_unique_id = f"{appliance.info.ha_id}-Door"
        self._attr_name = f"{appliance.info.name} Door"

    async def async_added_to_hass(self) -> None:
        """Call when entity is added to hass."""
        await super().async_added_to_hass()
        automations = automations_with_entity(self.hass, self.entity_id)
        scripts = scripts_with_entity(self.hass, self.entity_id)
        items = automations + scripts
        if not items:
            return

        entity_reg: er.EntityRegistry = er.async_get(self.hass)
        entity_automations = [
            automation_entity
            for automation_id in automations
            if (automation_entity := entity_reg.async_get(automation_id))
        ]
        entity_scripts = [
            script_entity
            for script_id in scripts
            if (script_entity := entity_reg.async_get(script_id))
        ]

        items_list = [
            f"- [{item.original_name}](/config/automation/edit/{item.unique_id})"
            for item in entity_automations
        ] + [
            f"- [{item.original_name}](/config/script/edit/{item.unique_id})"
            for item in entity_scripts
        ]

        async_create_issue(
            self.hass,
            DOMAIN,
            f"deprecated_binary_common_door_sensor_{self.entity_id}",
            breaks_in_ha_version="2025.5.0",
            is_fixable=True,
            is_persistent=True,
            severity=IssueSeverity.WARNING,
            translation_key="deprecated_binary_common_door_sensor",
            translation_placeholders={
                "entity": self.entity_id,
                "items": "\n".join(items_list),
            },
        )

    async def async_will_remove_from_hass(self) -> None:
        """Call when entity will be removed from hass."""
        await super().async_will_remove_from_hass()
        async_delete_issue(
            self.hass, DOMAIN, f"deprecated_binary_common_door_sensor_{self.entity_id}"
        )
