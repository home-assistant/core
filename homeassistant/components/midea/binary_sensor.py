"""Binary sensor for Midea Lan."""

from dataclasses import dataclass
from typing import override

from midealocal.const import DeviceType

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .entity import MideaConfigEntry, MideaEntity

PARALLEL_UPDATES = 0


@dataclass(kw_only=True, frozen=True)
class MideaBinarySensorEntityDescription(BinarySensorEntityDescription):
    """Description for a Midea binary sensor entity."""

    models: list[DeviceType] | None = None


BINARY_SENSORS: list[MideaBinarySensorEntityDescription] = [
    MideaBinarySensorEntityDescription(
        key="current_radar",
        device_class=BinarySensorDeviceClass.MOTION,
    ),
    MideaBinarySensorEntityDescription(
        key="door",
        device_class=BinarySensorDeviceClass.OPENING,
    ),
    MideaBinarySensorEntityDescription(
        key="door_warn",
        translation_key="door_warn",
        device_class=BinarySensorDeviceClass.PROBLEM,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    MideaBinarySensorEntityDescription(
        key="rinse_aid",
        translation_key="rinse_aid",
        device_class=BinarySensorDeviceClass.PROBLEM,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    MideaBinarySensorEntityDescription(
        key="salt",
        translation_key="salt",
        device_class=BinarySensorDeviceClass.PROBLEM,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    MideaBinarySensorEntityDescription(
        key="tank_full",
        translation_key="tank_full",
        device_class=BinarySensorDeviceClass.PROBLEM,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    MideaBinarySensorEntityDescription(
        key="water_pump_running",
        translation_key="water_pump_running",
        device_class=BinarySensorDeviceClass.RUNNING,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    MideaBinarySensorEntityDescription(
        key="filter_cleaning_reminder",
        translation_key="filter_cleaning_reminder",
        device_class=BinarySensorDeviceClass.PROBLEM,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    MideaBinarySensorEntityDescription(
        key="full_dust",
        translation_key="full_dust",
        device_class=BinarySensorDeviceClass.PROBLEM,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    MideaBinarySensorEntityDescription(
        key="fall_asleep_status",
        translation_key="fall_asleep_status",
        device_class=BinarySensorDeviceClass.RUNNING,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    MideaBinarySensorEntityDescription(
        key="night_mode",
        translation_key="night_mode",
        device_class=BinarySensorDeviceClass.RUNNING,
    ),
    MideaBinarySensorEntityDescription(
        key="screen_status",
        translation_key="screen_status",
        device_class=BinarySensorDeviceClass.RUNNING,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    MideaBinarySensorEntityDescription(
        key="led_status",
        translation_key="led_status",
        device_class=BinarySensorDeviceClass.RUNNING,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    MideaBinarySensorEntityDescription(
        key="arofene_link",
        translation_key="arofene_link",
        device_class=BinarySensorDeviceClass.PLUG,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    MideaBinarySensorEntityDescription(
        key="header_exist",
        translation_key="header_exist",
        device_class=BinarySensorDeviceClass.PLUG,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    MideaBinarySensorEntityDescription(
        key="protection",
        translation_key="protection",
        entity_category=EntityCategory.DIAGNOSTIC,
        models=[DeviceType.E3],
    ),
    MideaBinarySensorEntityDescription(
        key="heating",
        translation_key="heating",
        device_class=BinarySensorDeviceClass.RUNNING,
        entity_category=EntityCategory.DIAGNOSTIC,
        models=[DeviceType.E2],
    ),
    MideaBinarySensorEntityDescription(
        key="keep_warm",
        translation_key="keep_warm",
        device_class=BinarySensorDeviceClass.HEAT,
        entity_category=EntityCategory.DIAGNOSTIC,
        models=[DeviceType.E2],
    ),
]


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: MideaConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up sensors for device."""
    device = config_entry.runtime_data

    binary_sensors = [
        MideaBinarySensor(device, description)
        for description in BINARY_SENSORS
        if description.key in device.attributes
        and (description.models is None or device.device_type in description.models)
    ]
    async_add_entities(binary_sensors)


class MideaBinarySensor(MideaEntity, BinarySensorEntity):
    """Represent a Midea binary sensor."""

    @property
    @override
    def is_on(self) -> bool | None:
        """Return true if sensor state is on."""
        value = self._device.get_attribute(self.entity_description.key)
        if not isinstance(value, bool):
            return None
        return value
