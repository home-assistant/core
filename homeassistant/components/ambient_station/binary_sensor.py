"""Support for Ambient Weather Station binary sensors."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import ATTR_NAME
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import AmbientWeatherEntity
from .const import ATTR_LAST_DATA, DOMAIN

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


@dataclass
class AmbientBinarySensorDescriptionMixin:
    """Define an entity description mixin for binary sensors."""

    on_state: Literal[0, 1]


@dataclass
class AmbientBinarySensorDescription(
    BinarySensorEntityDescription, AmbientBinarySensorDescriptionMixin
):
    """Describe an Ambient PWS binary sensor."""


BINARY_SENSOR_DESCRIPTIONS = (
    AmbientBinarySensorDescription(
        key=TYPE_BATTOUT,
        name="Battery",
        device_class=BinarySensorDeviceClass.BATTERY,
        entity_category=EntityCategory.DIAGNOSTIC,
        on_state=0,
    ),
    AmbientBinarySensorDescription(
        key=TYPE_BATT1,
        name="Battery 1",
        device_class=BinarySensorDeviceClass.BATTERY,
        entity_category=EntityCategory.DIAGNOSTIC,
        on_state=0,
    ),
    AmbientBinarySensorDescription(
        key=TYPE_BATT2,
        name="Battery 2",
        device_class=BinarySensorDeviceClass.BATTERY,
        entity_category=EntityCategory.DIAGNOSTIC,
        on_state=0,
    ),
    AmbientBinarySensorDescription(
        key=TYPE_BATT3,
        name="Battery 3",
        device_class=BinarySensorDeviceClass.BATTERY,
        entity_category=EntityCategory.DIAGNOSTIC,
        on_state=0,
    ),
    AmbientBinarySensorDescription(
        key=TYPE_BATT4,
        name="Battery 4",
        device_class=BinarySensorDeviceClass.BATTERY,
        entity_category=EntityCategory.DIAGNOSTIC,
        on_state=0,
    ),
    AmbientBinarySensorDescription(
        key=TYPE_BATT5,
        name="Battery 5",
        device_class=BinarySensorDeviceClass.BATTERY,
        entity_category=EntityCategory.DIAGNOSTIC,
        on_state=0,
    ),
    AmbientBinarySensorDescription(
        key=TYPE_BATT6,
        name="Battery 6",
        device_class=BinarySensorDeviceClass.BATTERY,
        entity_category=EntityCategory.DIAGNOSTIC,
        on_state=0,
    ),
    AmbientBinarySensorDescription(
        key=TYPE_BATT7,
        name="Battery 7",
        device_class=BinarySensorDeviceClass.BATTERY,
        entity_category=EntityCategory.DIAGNOSTIC,
        on_state=0,
    ),
    AmbientBinarySensorDescription(
        key=TYPE_BATT8,
        name="Battery 8",
        device_class=BinarySensorDeviceClass.BATTERY,
        entity_category=EntityCategory.DIAGNOSTIC,
        on_state=0,
    ),
    AmbientBinarySensorDescription(
        key=TYPE_BATT9,
        name="Battery 9",
        device_class=BinarySensorDeviceClass.BATTERY,
        entity_category=EntityCategory.DIAGNOSTIC,
        on_state=0,
    ),
    AmbientBinarySensorDescription(
        key=TYPE_BATTIN,
        name="Interior battery",
        device_class=BinarySensorDeviceClass.BATTERY,
        entity_category=EntityCategory.DIAGNOSTIC,
        on_state=0,
    ),
    AmbientBinarySensorDescription(
        key=TYPE_BATT10,
        name="Battery 10",
        device_class=BinarySensorDeviceClass.BATTERY,
        entity_category=EntityCategory.DIAGNOSTIC,
        on_state=0,
    ),
    AmbientBinarySensorDescription(
        key=TYPE_BATT_SM1,
        name="Soil monitor battery 1",
        device_class=BinarySensorDeviceClass.BATTERY,
        entity_category=EntityCategory.DIAGNOSTIC,
        on_state=0,
    ),
    AmbientBinarySensorDescription(
        key=TYPE_BATT_SM2,
        name="Soil monitor battery 2",
        device_class=BinarySensorDeviceClass.BATTERY,
        entity_category=EntityCategory.DIAGNOSTIC,
        on_state=0,
    ),
    AmbientBinarySensorDescription(
        key=TYPE_BATT_SM3,
        name="Soil monitor battery 3",
        device_class=BinarySensorDeviceClass.BATTERY,
        entity_category=EntityCategory.DIAGNOSTIC,
        on_state=0,
    ),
    AmbientBinarySensorDescription(
        key=TYPE_BATT_SM4,
        name="Soil monitor battery 4",
        device_class=BinarySensorDeviceClass.BATTERY,
        entity_category=EntityCategory.DIAGNOSTIC,
        on_state=0,
    ),
    AmbientBinarySensorDescription(
        key=TYPE_BATT_SM5,
        name="Soil monitor battery 5",
        device_class=BinarySensorDeviceClass.BATTERY,
        entity_category=EntityCategory.DIAGNOSTIC,
        on_state=0,
    ),
    AmbientBinarySensorDescription(
        key=TYPE_BATT_SM6,
        name="Soil monitor battery 6",
        device_class=BinarySensorDeviceClass.BATTERY,
        entity_category=EntityCategory.DIAGNOSTIC,
        on_state=0,
    ),
    AmbientBinarySensorDescription(
        key=TYPE_BATT_SM7,
        name="Soil monitor battery 7",
        device_class=BinarySensorDeviceClass.BATTERY,
        entity_category=EntityCategory.DIAGNOSTIC,
        on_state=0,
    ),
    AmbientBinarySensorDescription(
        key=TYPE_BATT_SM8,
        name="Soil monitor battery 8",
        device_class=BinarySensorDeviceClass.BATTERY,
        entity_category=EntityCategory.DIAGNOSTIC,
        on_state=0,
    ),
    AmbientBinarySensorDescription(
        key=TYPE_BATT_SM9,
        name="Soil monitor battery 9",
        device_class=BinarySensorDeviceClass.BATTERY,
        entity_category=EntityCategory.DIAGNOSTIC,
        on_state=0,
    ),
    AmbientBinarySensorDescription(
        key=TYPE_BATT_SM10,
        name="Soil monitor battery 10",
        device_class=BinarySensorDeviceClass.BATTERY,
        entity_category=EntityCategory.DIAGNOSTIC,
        on_state=0,
    ),
    AmbientBinarySensorDescription(
        key=TYPE_BATT_CO2,
        name="CO2 battery",
        device_class=BinarySensorDeviceClass.BATTERY,
        entity_category=EntityCategory.DIAGNOSTIC,
        on_state=0,
    ),
    AmbientBinarySensorDescription(
        key=TYPE_BATT_LIGHTNING,
        name="Lightning detector battery",
        device_class=BinarySensorDeviceClass.BATTERY,
        entity_category=EntityCategory.DIAGNOSTIC,
        on_state=0,
    ),
    AmbientBinarySensorDescription(
        key=TYPE_PM25IN_BATT,
        name="PM25 indoor battery",
        device_class=BinarySensorDeviceClass.BATTERY,
        entity_category=EntityCategory.DIAGNOSTIC,
        on_state=0,
    ),
    AmbientBinarySensorDescription(
        key=TYPE_PM25_BATT,
        name="PM25 battery",
        device_class=BinarySensorDeviceClass.BATTERY,
        entity_category=EntityCategory.DIAGNOSTIC,
        on_state=0,
    ),
    AmbientBinarySensorDescription(
        key=TYPE_RELAY1,
        name="Relay 1",
        device_class=BinarySensorDeviceClass.CONNECTIVITY,
        entity_category=EntityCategory.DIAGNOSTIC,
        on_state=1,
    ),
    AmbientBinarySensorDescription(
        key=TYPE_RELAY2,
        name="Relay 2",
        device_class=BinarySensorDeviceClass.CONNECTIVITY,
        entity_category=EntityCategory.DIAGNOSTIC,
        on_state=1,
    ),
    AmbientBinarySensorDescription(
        key=TYPE_RELAY3,
        name="Relay 3",
        device_class=BinarySensorDeviceClass.CONNECTIVITY,
        entity_category=EntityCategory.DIAGNOSTIC,
        on_state=1,
    ),
    AmbientBinarySensorDescription(
        key=TYPE_RELAY4,
        name="Relay 4",
        device_class=BinarySensorDeviceClass.CONNECTIVITY,
        entity_category=EntityCategory.DIAGNOSTIC,
        on_state=1,
    ),
    AmbientBinarySensorDescription(
        key=TYPE_RELAY5,
        name="Relay 5",
        device_class=BinarySensorDeviceClass.CONNECTIVITY,
        entity_category=EntityCategory.DIAGNOSTIC,
        on_state=1,
    ),
    AmbientBinarySensorDescription(
        key=TYPE_RELAY6,
        name="Relay 6",
        device_class=BinarySensorDeviceClass.CONNECTIVITY,
        entity_category=EntityCategory.DIAGNOSTIC,
        on_state=1,
    ),
    AmbientBinarySensorDescription(
        key=TYPE_RELAY7,
        name="Relay 7",
        device_class=BinarySensorDeviceClass.CONNECTIVITY,
        entity_category=EntityCategory.DIAGNOSTIC,
        on_state=1,
    ),
    AmbientBinarySensorDescription(
        key=TYPE_RELAY8,
        name="Relay 8",
        device_class=BinarySensorDeviceClass.CONNECTIVITY,
        entity_category=EntityCategory.DIAGNOSTIC,
        on_state=1,
    ),
    AmbientBinarySensorDescription(
        key=TYPE_RELAY9,
        name="Relay 9",
        device_class=BinarySensorDeviceClass.CONNECTIVITY,
        entity_category=EntityCategory.DIAGNOSTIC,
        on_state=1,
    ),
    AmbientBinarySensorDescription(
        key=TYPE_RELAY10,
        name="Relay 10",
        device_class=BinarySensorDeviceClass.CONNECTIVITY,
        entity_category=EntityCategory.DIAGNOSTIC,
        on_state=1,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up Ambient PWS binary sensors based on a config entry."""
    ambient = hass.data[DOMAIN][entry.entry_id]

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
        self._attr_is_on = (
            self._ambient.stations[self._mac_address][ATTR_LAST_DATA][
                self.entity_description.key
            ]
            == self.entity_description.on_state
        )
