"""Support for Ambient Weather Station binary sensors."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.const import ATTR_NAME, EntityCategory
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import AmbientStationConfigEntry
from .const import ATTR_LAST_DATA
from .entity import AmbientWeatherEntity

TYPE_BATT1 = "batt1"
TYPE_BATT10 = "batt10"
TYPE_BATT2 = "batt2"
TYPE_BATT3 = "batt3"
TYPE_BATT4 = "batt4"
TYPE_BATT5 = "batt5"
TYPE_BATT6 = "batt6"
TYPE_BATT7 = "batt7"
TYPE_BATT8 = "batt8"
TYPE_BATT9 = "batt9"
TYPE_BATTIN = "battin"
TYPE_BATTOUT = "battout"
TYPE_BATT_CO2 = "batt_co2"
TYPE_BATT_LEAK1 = "batleak1"
TYPE_BATT_LEAK2 = "batleak2"
TYPE_BATT_LEAK3 = "batleak3"
TYPE_BATT_LEAK4 = "batleak4"
TYPE_BATT_LIGHTNING = "batt_lightning"
TYPE_BATT_SM1 = "battsm1"
TYPE_BATT_SM10 = "battsm10"
TYPE_BATT_SM2 = "battsm2"
TYPE_BATT_SM3 = "battsm3"
TYPE_BATT_SM4 = "battsm4"
TYPE_BATT_SM5 = "battsm5"
TYPE_BATT_SM6 = "battsm6"
TYPE_BATT_SM7 = "battsm7"
TYPE_BATT_SM8 = "battsm8"
TYPE_BATT_SM9 = "battsm9"
TYPE_LEAK1 = "leak1"
TYPE_LEAK2 = "leak2"
TYPE_LEAK3 = "leak3"
TYPE_LEAK4 = "leak4"
TYPE_PM25IN_BATT = "batt_25in"
TYPE_PM25_BATT = "batt_25"
TYPE_RELAY1 = "relay1"
TYPE_RELAY10 = "relay10"
TYPE_RELAY2 = "relay2"
TYPE_RELAY3 = "relay3"
TYPE_RELAY4 = "relay4"
TYPE_RELAY5 = "relay5"
TYPE_RELAY6 = "relay6"
TYPE_RELAY7 = "relay7"
TYPE_RELAY8 = "relay8"
TYPE_RELAY9 = "relay9"


@dataclass(frozen=True, kw_only=True)
class AmbientBinarySensorDescription(BinarySensorEntityDescription):
    """Describe an Ambient PWS binary sensor."""

    on_state: Literal[0, 1]


BINARY_SENSOR_DESCRIPTIONS = (
    AmbientBinarySensorDescription(
        key=TYPE_BATTOUT,
        device_class=BinarySensorDeviceClass.BATTERY,
        entity_category=EntityCategory.DIAGNOSTIC,
        on_state=0,
    ),
    AmbientBinarySensorDescription(
        key=TYPE_BATT1,
        translation_key="battery_1",
        device_class=BinarySensorDeviceClass.BATTERY,
        entity_category=EntityCategory.DIAGNOSTIC,
        on_state=0,
    ),
    AmbientBinarySensorDescription(
        key=TYPE_BATT2,
        translation_key="battery_2",
        device_class=BinarySensorDeviceClass.BATTERY,
        entity_category=EntityCategory.DIAGNOSTIC,
        on_state=0,
    ),
    AmbientBinarySensorDescription(
        key=TYPE_BATT3,
        translation_key="battery_3",
        device_class=BinarySensorDeviceClass.BATTERY,
        entity_category=EntityCategory.DIAGNOSTIC,
        on_state=0,
    ),
    AmbientBinarySensorDescription(
        key=TYPE_BATT4,
        translation_key="battery_4",
        device_class=BinarySensorDeviceClass.BATTERY,
        entity_category=EntityCategory.DIAGNOSTIC,
        on_state=0,
    ),
    AmbientBinarySensorDescription(
        key=TYPE_BATT5,
        translation_key="battery_5",
        device_class=BinarySensorDeviceClass.BATTERY,
        entity_category=EntityCategory.DIAGNOSTIC,
        on_state=0,
    ),
    AmbientBinarySensorDescription(
        key=TYPE_BATT6,
        translation_key="battery_6",
        device_class=BinarySensorDeviceClass.BATTERY,
        entity_category=EntityCategory.DIAGNOSTIC,
        on_state=0,
    ),
    AmbientBinarySensorDescription(
        key=TYPE_BATT7,
        translation_key="battery_7",
        device_class=BinarySensorDeviceClass.BATTERY,
        entity_category=EntityCategory.DIAGNOSTIC,
        on_state=0,
    ),
    AmbientBinarySensorDescription(
        key=TYPE_BATT8,
        translation_key="battery_8",
        device_class=BinarySensorDeviceClass.BATTERY,
        entity_category=EntityCategory.DIAGNOSTIC,
        on_state=0,
    ),
    AmbientBinarySensorDescription(
        key=TYPE_BATT9,
        translation_key="battery_9",
        device_class=BinarySensorDeviceClass.BATTERY,
        entity_category=EntityCategory.DIAGNOSTIC,
        on_state=0,
    ),
    AmbientBinarySensorDescription(
        key=TYPE_BATTIN,
        translation_key="interior_battery",
        device_class=BinarySensorDeviceClass.BATTERY,
        entity_category=EntityCategory.DIAGNOSTIC,
        on_state=0,
    ),
    AmbientBinarySensorDescription(
        key=TYPE_BATT10,
        translation_key="battery_10",
        device_class=BinarySensorDeviceClass.BATTERY,
        entity_category=EntityCategory.DIAGNOSTIC,
        on_state=0,
    ),
    AmbientBinarySensorDescription(
        key=TYPE_BATT_LEAK1,
        translation_key="leak_detector_battery_1",
        device_class=BinarySensorDeviceClass.BATTERY,
        entity_category=EntityCategory.DIAGNOSTIC,
        on_state=1,
    ),
    AmbientBinarySensorDescription(
        key=TYPE_BATT_LEAK2,
        translation_key="leak_detector_battery_2",
        device_class=BinarySensorDeviceClass.BATTERY,
        entity_category=EntityCategory.DIAGNOSTIC,
        on_state=1,
    ),
    AmbientBinarySensorDescription(
        key=TYPE_BATT_LEAK3,
        translation_key="leak_detector_battery_3",
        device_class=BinarySensorDeviceClass.BATTERY,
        entity_category=EntityCategory.DIAGNOSTIC,
        on_state=1,
    ),
    AmbientBinarySensorDescription(
        key=TYPE_BATT_LEAK4,
        translation_key="leak_detector_battery_4",
        device_class=BinarySensorDeviceClass.BATTERY,
        entity_category=EntityCategory.DIAGNOSTIC,
        on_state=1,
    ),
    AmbientBinarySensorDescription(
        key=TYPE_BATT_SM1,
        translation_key="soil_monitor_battery_1",
        device_class=BinarySensorDeviceClass.BATTERY,
        entity_category=EntityCategory.DIAGNOSTIC,
        on_state=0,
    ),
    AmbientBinarySensorDescription(
        key=TYPE_BATT_SM2,
        translation_key="soil_monitor_battery_2",
        device_class=BinarySensorDeviceClass.BATTERY,
        entity_category=EntityCategory.DIAGNOSTIC,
        on_state=0,
    ),
    AmbientBinarySensorDescription(
        key=TYPE_BATT_SM3,
        translation_key="soil_monitor_battery_3",
        device_class=BinarySensorDeviceClass.BATTERY,
        entity_category=EntityCategory.DIAGNOSTIC,
        on_state=0,
    ),
    AmbientBinarySensorDescription(
        key=TYPE_BATT_SM4,
        translation_key="soil_monitor_battery_4",
        device_class=BinarySensorDeviceClass.BATTERY,
        entity_category=EntityCategory.DIAGNOSTIC,
        on_state=0,
    ),
    AmbientBinarySensorDescription(
        key=TYPE_BATT_SM5,
        translation_key="soil_monitor_battery_5",
        device_class=BinarySensorDeviceClass.BATTERY,
        entity_category=EntityCategory.DIAGNOSTIC,
        on_state=0,
    ),
    AmbientBinarySensorDescription(
        key=TYPE_BATT_SM6,
        translation_key="soil_monitor_battery_6",
        device_class=BinarySensorDeviceClass.BATTERY,
        entity_category=EntityCategory.DIAGNOSTIC,
        on_state=0,
    ),
    AmbientBinarySensorDescription(
        key=TYPE_BATT_SM7,
        translation_key="soil_monitor_battery_7",
        device_class=BinarySensorDeviceClass.BATTERY,
        entity_category=EntityCategory.DIAGNOSTIC,
        on_state=0,
    ),
    AmbientBinarySensorDescription(
        key=TYPE_BATT_SM8,
        translation_key="soil_monitor_battery_8",
        device_class=BinarySensorDeviceClass.BATTERY,
        entity_category=EntityCategory.DIAGNOSTIC,
        on_state=0,
    ),
    AmbientBinarySensorDescription(
        key=TYPE_BATT_SM9,
        translation_key="soil_monitor_battery_9",
        device_class=BinarySensorDeviceClass.BATTERY,
        entity_category=EntityCategory.DIAGNOSTIC,
        on_state=0,
    ),
    AmbientBinarySensorDescription(
        key=TYPE_BATT_SM10,
        translation_key="soil_monitor_battery_10",
        device_class=BinarySensorDeviceClass.BATTERY,
        entity_category=EntityCategory.DIAGNOSTIC,
        on_state=0,
    ),
    AmbientBinarySensorDescription(
        key=TYPE_BATT_CO2,
        translation_key="co2_battery",
        device_class=BinarySensorDeviceClass.BATTERY,
        entity_category=EntityCategory.DIAGNOSTIC,
        on_state=0,
    ),
    AmbientBinarySensorDescription(
        key=TYPE_BATT_LIGHTNING,
        translation_key="lightning_detector_battery",
        device_class=BinarySensorDeviceClass.BATTERY,
        entity_category=EntityCategory.DIAGNOSTIC,
        on_state=1,
    ),
    AmbientBinarySensorDescription(
        key=TYPE_LEAK1,
        translation_key="leak_detector_1",
        device_class=BinarySensorDeviceClass.MOISTURE,
        on_state=1,
    ),
    AmbientBinarySensorDescription(
        key=TYPE_LEAK2,
        translation_key="leak_detector_2",
        device_class=BinarySensorDeviceClass.MOISTURE,
        on_state=1,
    ),
    AmbientBinarySensorDescription(
        key=TYPE_LEAK3,
        translation_key="leak_detector_3",
        device_class=BinarySensorDeviceClass.MOISTURE,
        on_state=1,
    ),
    AmbientBinarySensorDescription(
        key=TYPE_LEAK4,
        translation_key="leak_detector_4",
        device_class=BinarySensorDeviceClass.MOISTURE,
        on_state=1,
    ),
    AmbientBinarySensorDescription(
        key=TYPE_PM25IN_BATT,
        translation_key="pm25_indoor_battery",
        device_class=BinarySensorDeviceClass.BATTERY,
        entity_category=EntityCategory.DIAGNOSTIC,
        on_state=0,
    ),
    AmbientBinarySensorDescription(
        key=TYPE_PM25_BATT,
        translation_key="pm25_battery",
        device_class=BinarySensorDeviceClass.BATTERY,
        entity_category=EntityCategory.DIAGNOSTIC,
        on_state=0,
    ),
    AmbientBinarySensorDescription(
        key=TYPE_RELAY1,
        translation_key="relay_1",
        device_class=BinarySensorDeviceClass.CONNECTIVITY,
        entity_category=EntityCategory.DIAGNOSTIC,
        on_state=1,
    ),
    AmbientBinarySensorDescription(
        key=TYPE_RELAY2,
        translation_key="relay_2",
        device_class=BinarySensorDeviceClass.CONNECTIVITY,
        entity_category=EntityCategory.DIAGNOSTIC,
        on_state=1,
    ),
    AmbientBinarySensorDescription(
        key=TYPE_RELAY3,
        translation_key="relay_3",
        device_class=BinarySensorDeviceClass.CONNECTIVITY,
        entity_category=EntityCategory.DIAGNOSTIC,
        on_state=1,
    ),
    AmbientBinarySensorDescription(
        key=TYPE_RELAY4,
        translation_key="relay_4",
        device_class=BinarySensorDeviceClass.CONNECTIVITY,
        entity_category=EntityCategory.DIAGNOSTIC,
        on_state=1,
    ),
    AmbientBinarySensorDescription(
        key=TYPE_RELAY5,
        translation_key="relay_5",
        device_class=BinarySensorDeviceClass.CONNECTIVITY,
        entity_category=EntityCategory.DIAGNOSTIC,
        on_state=1,
    ),
    AmbientBinarySensorDescription(
        key=TYPE_RELAY6,
        translation_key="relay_6",
        device_class=BinarySensorDeviceClass.CONNECTIVITY,
        entity_category=EntityCategory.DIAGNOSTIC,
        on_state=1,
    ),
    AmbientBinarySensorDescription(
        key=TYPE_RELAY7,
        translation_key="relay_7",
        device_class=BinarySensorDeviceClass.CONNECTIVITY,
        entity_category=EntityCategory.DIAGNOSTIC,
        on_state=1,
    ),
    AmbientBinarySensorDescription(
        key=TYPE_RELAY8,
        translation_key="relay_8",
        device_class=BinarySensorDeviceClass.CONNECTIVITY,
        entity_category=EntityCategory.DIAGNOSTIC,
        on_state=1,
    ),
    AmbientBinarySensorDescription(
        key=TYPE_RELAY9,
        translation_key="relay_9",
        device_class=BinarySensorDeviceClass.CONNECTIVITY,
        entity_category=EntityCategory.DIAGNOSTIC,
        on_state=1,
    ),
    AmbientBinarySensorDescription(
        key=TYPE_RELAY10,
        translation_key="relay_10",
        device_class=BinarySensorDeviceClass.CONNECTIVITY,
        entity_category=EntityCategory.DIAGNOSTIC,
        on_state=1,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: AmbientStationConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Ambient PWS binary sensors based on a config entry."""
    ambient = entry.runtime_data

    async_add_entities(
        AmbientWeatherBinarySensor(
            ambient, mac_address, station[ATTR_NAME], description
        )
        for mac_address, station in ambient.stations.items()
        for description in BINARY_SENSOR_DESCRIPTIONS
        if description.key in station[ATTR_LAST_DATA]
    )


class AmbientWeatherBinarySensor(AmbientWeatherEntity, BinarySensorEntity):
    """Define an Ambient binary sensor."""

    entity_description: AmbientBinarySensorDescription

    @callback
    def update_from_latest_data(self) -> None:
        """Fetch new state data for the entity."""
        description = self.entity_description
        last_data = self._ambient.stations[self._mac_address][ATTR_LAST_DATA]
        self._attr_is_on = last_data[description.key] == description.on_state
