"""Support for binary sensors through the SmartThings cloud API."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from pysmartthings import Attribute, Capability, Category, SmartThings, Status

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import FullDevice, SmartThingsConfigEntry
from .const import INVALID_SWITCH_CATEGORIES, MAIN
from .entity import SmartThingsEntity


@dataclass(frozen=True, kw_only=True)
class SmartThingsBinarySensorEntityDescription(BinarySensorEntityDescription):
    """Describe a SmartThings binary sensor entity."""

    is_on_key: str
    category_device_class: dict[Category | str, BinarySensorDeviceClass] | None = None
    category: set[Category] | None = None
    exists_fn: (
        Callable[
            [str, dict[str, dict[Capability | str, dict[Attribute | str, Status]]]],
            bool,
        ]
        | None
    ) = None
    component_translation_key: dict[str, str] | None = None


CAPABILITY_TO_SENSORS: dict[
    Capability, dict[Attribute, SmartThingsBinarySensorEntityDescription]
] = {
    Capability.ACCELERATION_SENSOR: {
        Attribute.ACCELERATION: SmartThingsBinarySensorEntityDescription(
            key=Attribute.ACCELERATION,
            translation_key="acceleration",
            device_class=BinarySensorDeviceClass.MOVING,
            is_on_key="active",
        )
    },
    Capability.CONTACT_SENSOR: {
        Attribute.CONTACT: SmartThingsBinarySensorEntityDescription(
            key=Attribute.CONTACT,
            device_class=BinarySensorDeviceClass.DOOR,
            is_on_key="open",
            category_device_class={
                Category.GARAGE_DOOR: BinarySensorDeviceClass.GARAGE_DOOR,
                Category.DOOR: BinarySensorDeviceClass.DOOR,
                Category.WINDOW: BinarySensorDeviceClass.WINDOW,
            },
            exists_fn=lambda component, status: (
                not ("freezer" in status and "cooler" in status)
                if component == MAIN
                else True
            ),
            component_translation_key={
                "freezer": "freezer_door",
                "cooler": "cooler_door",
                "cvroom": "cool_select_plus_door",
            },
        )
    },
    Capability.CUSTOM_DRYER_WRINKLE_PREVENT: {
        Attribute.OPERATING_STATE: SmartThingsBinarySensorEntityDescription(
            key=Attribute.OPERATING_STATE,
            translation_key="dryer_wrinkle_prevent_active",
            is_on_key="running",
            entity_category=EntityCategory.DIAGNOSTIC,
        )
    },
    Capability.CUSTOM_WATER_FILTER: {
        Attribute.WATER_FILTER_STATUS: SmartThingsBinarySensorEntityDescription(
            key=Attribute.WATER_FILTER_STATUS,
            translation_key="filter_status",
            device_class=BinarySensorDeviceClass.PROBLEM,
            is_on_key="replace",
        )
    },
    Capability.SAMSUNG_CE_STEAM_CLOSET_KEEP_FRESH_MODE: {
        Attribute.OPERATING_STATE: SmartThingsBinarySensorEntityDescription(
            key=Attribute.OPERATING_STATE,
            translation_key="keep_fresh_mode_active",
            is_on_key="running",
            entity_category=EntityCategory.DIAGNOSTIC,
        )
    },
    Capability.FILTER_STATUS: {
        Attribute.FILTER_STATUS: SmartThingsBinarySensorEntityDescription(
            key=Attribute.FILTER_STATUS,
            translation_key="filter_status",
            device_class=BinarySensorDeviceClass.PROBLEM,
            is_on_key="replace",
        )
    },
    Capability.SAMSUNG_CE_KIDS_LOCK: {
        Attribute.LOCK_STATE: SmartThingsBinarySensorEntityDescription(
            key=Attribute.LOCK_STATE,
            translation_key="child_lock",
            is_on_key="locked",
        )
    },
    Capability.MOTION_SENSOR: {
        Attribute.MOTION: SmartThingsBinarySensorEntityDescription(
            key=Attribute.MOTION,
            device_class=BinarySensorDeviceClass.MOTION,
            is_on_key="active",
        )
    },
    Capability.PRESENCE_SENSOR: {
        Attribute.PRESENCE: SmartThingsBinarySensorEntityDescription(
            key=Attribute.PRESENCE,
            device_class=BinarySensorDeviceClass.PRESENCE,
            is_on_key="present",
        )
    },
    Capability.REMOTE_CONTROL_STATUS: {
        Attribute.REMOTE_CONTROL_ENABLED: SmartThingsBinarySensorEntityDescription(
            key=Attribute.REMOTE_CONTROL_ENABLED,
            translation_key="remote_control",
            is_on_key="true",
            component_translation_key={
                "sub": "sub_remote_control",
            },
        )
    },
    Capability.SOUND_SENSOR: {
        Attribute.SOUND: SmartThingsBinarySensorEntityDescription(
            key=Attribute.SOUND,
            device_class=BinarySensorDeviceClass.SOUND,
            is_on_key="detected",
        )
    },
    Capability.SWITCH: {
        Attribute.SWITCH: SmartThingsBinarySensorEntityDescription(
            key=Attribute.SWITCH,
            device_class=BinarySensorDeviceClass.POWER,
            is_on_key="on",
            category=INVALID_SWITCH_CATEGORIES,
        )
    },
    Capability.TAMPER_ALERT: {
        Attribute.TAMPER: SmartThingsBinarySensorEntityDescription(
            key=Attribute.TAMPER,
            device_class=BinarySensorDeviceClass.TAMPER,
            is_on_key="detected",
            entity_category=EntityCategory.DIAGNOSTIC,
        )
    },
    Capability.WATER_SENSOR: {
        Attribute.WATER: SmartThingsBinarySensorEntityDescription(
            key=Attribute.WATER,
            device_class=BinarySensorDeviceClass.MOISTURE,
            is_on_key="wet",
        )
    },
    Capability.SAMSUNG_CE_DOOR_STATE: {
        Attribute.DOOR_STATE: SmartThingsBinarySensorEntityDescription(
            key=Attribute.DOOR_STATE,
            translation_key="door",
            device_class=BinarySensorDeviceClass.OPENING,
            is_on_key="open",
        )
    },
    Capability.GAS_DETECTOR: {
        Attribute.GAS: SmartThingsBinarySensorEntityDescription(
            key=Attribute.GAS,
            device_class=BinarySensorDeviceClass.GAS,
            is_on_key="detected",
        )
    },
}


def get_main_component_category(
    device: FullDevice,
) -> Category | str:
    """Get the main component of a device."""
    main = device.device.components[MAIN]
    return main.user_category or main.manufacturer_category


async def async_setup_entry(
    hass: HomeAssistant,
    entry: SmartThingsConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Add binary sensors for a config entry."""
    entry_data = entry.runtime_data

    async_add_entities(
        SmartThingsBinarySensor(
            entry_data.client,
            device,
            description,
            capability,
            attribute,
            component,
        )
        for device in entry_data.devices.values()
        for capability, attribute_map in CAPABILITY_TO_SENSORS.items()
        for attribute, description in attribute_map.items()
        for component in device.status
        if (
            capability in device.status[component]
            and (
                component == MAIN
                or (
                    description.component_translation_key is not None
                    and component in description.component_translation_key
                )
            )
            and (
                description.exists_fn is None
                or description.exists_fn(component, device.status)
            )
            and (
                not description.category
                or get_main_component_category(device) in description.category
            )
        )
    )


class SmartThingsBinarySensor(SmartThingsEntity, BinarySensorEntity):
    """Define a SmartThings Binary Sensor."""

    entity_description: SmartThingsBinarySensorEntityDescription

    def __init__(
        self,
        client: SmartThings,
        device: FullDevice,
        entity_description: SmartThingsBinarySensorEntityDescription,
        capability: Capability,
        attribute: Attribute,
        component: str,
    ) -> None:
        """Init the class."""
        super().__init__(client, device, {capability}, component=component)
        self._attribute = attribute
        self.capability = capability
        self.entity_description = entity_description
        self._attr_unique_id = f"{device.device.device_id}_{component}_{capability}_{attribute}_{attribute}"
        if (
            entity_description.category_device_class
            and (category := get_main_component_category(device))
            in entity_description.category_device_class
        ):
            self._attr_device_class = entity_description.category_device_class[category]
            self._attr_name = None
        if (
            entity_description.component_translation_key is not None
            and (
                translation_key := entity_description.component_translation_key.get(
                    component
                )
            )
            is not None
        ):
            self._attr_translation_key = translation_key

    @property
    def is_on(self) -> bool:
        """Return true if the binary sensor is on."""
        return (
            self.get_attribute_value(self.capability, self._attribute)
            == self.entity_description.is_on_key
        )
