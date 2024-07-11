"""Support for 1-Wire binary sensors."""

from __future__ import annotations

from dataclasses import dataclass
import os

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import OneWireConfigEntry
from .const import DEVICE_KEYS_0_3, DEVICE_KEYS_0_7, DEVICE_KEYS_A_B, READ_MODE_BOOL
from .onewire_entities import OneWireEntity, OneWireEntityDescription
from .onewirehub import OneWireHub


@dataclass(frozen=True)
class OneWireBinarySensorEntityDescription(
    OneWireEntityDescription, BinarySensorEntityDescription
):
    """Class describing OneWire binary sensor entities."""


DEVICE_BINARY_SENSORS: dict[str, tuple[OneWireBinarySensorEntityDescription, ...]] = {
    "12": tuple(
        OneWireBinarySensorEntityDescription(
            key=f"sensed.{device_key}",
            entity_registry_enabled_default=False,
            read_mode=READ_MODE_BOOL,
            translation_key="sensed_id",
            translation_placeholders={"id": str(device_key)},
        )
        for device_key in DEVICE_KEYS_A_B
    ),
    "29": tuple(
        OneWireBinarySensorEntityDescription(
            key=f"sensed.{device_key}",
            entity_registry_enabled_default=False,
            read_mode=READ_MODE_BOOL,
            translation_key="sensed_id",
            translation_placeholders={"id": str(device_key)},
        )
        for device_key in DEVICE_KEYS_0_7
    ),
    "3A": tuple(
        OneWireBinarySensorEntityDescription(
            key=f"sensed.{device_key}",
            entity_registry_enabled_default=False,
            read_mode=READ_MODE_BOOL,
            translation_key="sensed_id",
            translation_placeholders={"id": str(device_key)},
        )
        for device_key in DEVICE_KEYS_A_B
    ),
    "EF": (),  # "HobbyBoard": special
}

# EF sensors are usually hobbyboards specialized sensors.
HOBBYBOARD_EF: dict[str, tuple[OneWireBinarySensorEntityDescription, ...]] = {
    "HB_HUB": tuple(
        OneWireBinarySensorEntityDescription(
            key=f"hub/short.{device_key}",
            entity_registry_enabled_default=False,
            read_mode=READ_MODE_BOOL,
            entity_category=EntityCategory.DIAGNOSTIC,
            device_class=BinarySensorDeviceClass.PROBLEM,
            translation_key="hub_short_id",
            translation_placeholders={"id": str(device_key)},
        )
        for device_key in DEVICE_KEYS_0_3
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
    config_entry: OneWireConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up 1-Wire platform."""
    entities = await hass.async_add_executor_job(
        get_entities, config_entry.runtime_data
    )
    async_add_entities(entities, True)


def get_entities(onewire_hub: OneWireHub) -> list[OneWireBinarySensor]:
    """Get a list of entities."""
    if not onewire_hub.devices:
        return []

    entities: list[OneWireBinarySensor] = []
    for device in onewire_hub.devices:
        family = device.family
        device_id = device.id
        device_type = device.type
        device_info = device.device_info
        device_sub_type = "std"
        if device_type and "EF" in family:
            device_sub_type = "HobbyBoard"
            family = device_type

        if family not in get_sensor_types(device_sub_type):
            continue
        for description in get_sensor_types(device_sub_type)[family]:
            device_file = os.path.join(os.path.split(device.path)[0], description.key)
            entities.append(
                OneWireBinarySensor(
                    description=description,
                    device_id=device_id,
                    device_file=device_file,
                    device_info=device_info,
                    owproxy=onewire_hub.owproxy,
                )
            )

    return entities


class OneWireBinarySensor(OneWireEntity, BinarySensorEntity):
    """Implementation of a 1-Wire binary sensor."""

    entity_description: OneWireBinarySensorEntityDescription

    @property
    def is_on(self) -> bool | None:
        """Return true if sensor is on."""
        if self._state is None:
            return None
        return bool(self._state)
