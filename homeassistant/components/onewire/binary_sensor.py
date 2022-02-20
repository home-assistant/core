"""Support for 1-Wire binary sensors."""
from __future__ import annotations

from dataclasses import dataclass
import os
from typing import TYPE_CHECKING

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_TYPE
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import (
    CONF_TYPE_OWSERVER,
    DEVICE_KEYS_0_3,
    DEVICE_KEYS_0_7,
    DEVICE_KEYS_A_B,
    DOMAIN,
    READ_MODE_BOOL,
)
from .model import OWServerDeviceDescription
from .onewire_entities import OneWireEntityDescription, OneWireProxyEntity
from .onewirehub import OneWireHub


@dataclass
class OneWireBinarySensorEntityDescription(
    OneWireEntityDescription, BinarySensorEntityDescription
):
    """Class describing OneWire binary sensor entities."""


DEVICE_BINARY_SENSORS: dict[str, tuple[OneWireBinarySensorEntityDescription, ...]] = {
    "12": tuple(
        OneWireBinarySensorEntityDescription(
            key=f"sensed.{id}",
            entity_registry_enabled_default=False,
            name=f"Sensed {id}",
            read_mode=READ_MODE_BOOL,
        )
        for id in DEVICE_KEYS_A_B
    ),
    "29": tuple(
        OneWireBinarySensorEntityDescription(
            key=f"sensed.{id}",
            entity_registry_enabled_default=False,
            name=f"Sensed {id}",
            read_mode=READ_MODE_BOOL,
        )
        for id in DEVICE_KEYS_0_7
    ),
    "3A": tuple(
        OneWireBinarySensorEntityDescription(
            key=f"sensed.{id}",
            entity_registry_enabled_default=False,
            name=f"Sensed {id}",
            read_mode=READ_MODE_BOOL,
        )
        for id in DEVICE_KEYS_A_B
    ),
    "EF": (),  # "HobbyBoard": special
}

# EF sensors are usually hobbyboards specialized sensors.
HOBBYBOARD_EF: dict[str, tuple[OneWireBinarySensorEntityDescription, ...]] = {
    "HB_HUB": tuple(
        OneWireBinarySensorEntityDescription(
            key=f"hub/short.{id}",
            entity_registry_enabled_default=False,
            name=f"Hub Short on Branch {id}",
            read_mode=READ_MODE_BOOL,
            entity_category=EntityCategory.DIAGNOSTIC,
            device_class=BinarySensorDeviceClass.PROBLEM,
        )
        for id in DEVICE_KEYS_0_3
    ),
}


def get_sensor_types(
    device_sub_type: str,
) -> dict[str, tuple[OneWireBinarySensorEntityDescription, ...]]:
    """Return the proper info array for the device type."""
    if "HobbyBoard" in device_sub_type:
        return HOBBYBOARD_EF
    return DEVICE_BINARY_SENSORS


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up 1-Wire platform."""
    # Only OWServer implementation works with binary sensors
    if config_entry.data[CONF_TYPE] == CONF_TYPE_OWSERVER:
        onewirehub = hass.data[DOMAIN][config_entry.entry_id]

        entities = await hass.async_add_executor_job(get_entities, onewirehub)
        async_add_entities(entities, True)


def get_entities(onewirehub: OneWireHub) -> list[BinarySensorEntity]:
    """Get a list of entities."""
    if not onewirehub.devices:
        return []

    entities: list[BinarySensorEntity] = []
    for device in onewirehub.devices:
        if TYPE_CHECKING:
            assert isinstance(device, OWServerDeviceDescription)
        family = device.family
        device_id = device.id
        device_type = device.type
        device_info = device.device_info
        device_sub_type = "std"
        if "EF" in family:
            device_sub_type = "HobbyBoard"
            family = device_type

        if family not in get_sensor_types(device_sub_type):
            continue
        for description in get_sensor_types(device_sub_type)[family]:
            device_file = os.path.join(os.path.split(device.path)[0], description.key)
            name = f"{device_id} {description.name}"
            entities.append(
                OneWireProxyBinarySensor(
                    description=description,
                    device_id=device_id,
                    device_file=device_file,
                    device_info=device_info,
                    name=name,
                    owproxy=onewirehub.owproxy,
                )
            )

    return entities


class OneWireProxyBinarySensor(OneWireProxyEntity, BinarySensorEntity):
    """Implementation of a 1-Wire binary sensor."""

    entity_description: OneWireBinarySensorEntityDescription

    @property
    def is_on(self) -> bool:
        """Return true if sensor is on."""
        return bool(self._state)
