"""Support for 1-Wire environment switches."""
from __future__ import annotations

from dataclasses import dataclass
import os
from typing import Any

from homeassistant.components.switch import SwitchEntity, SwitchEntityDescription
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import (
    DEVICE_KEYS_0_3,
    DEVICE_KEYS_0_7,
    DEVICE_KEYS_A_B,
    DOMAIN,
    READ_MODE_BOOL,
)
from .onewire_entities import OneWireEntity, OneWireEntityDescription
from .onewirehub import OneWireHub


@dataclass
class OneWireSwitchEntityDescription(OneWireEntityDescription, SwitchEntityDescription):
    """Class describing OneWire switch entities."""


DEVICE_SWITCHES: dict[str, tuple[OneWireEntityDescription, ...]] = {
    "05": (
        OneWireSwitchEntityDescription(
            key="PIO",
            entity_registry_enabled_default=False,
            name="PIO",
            read_mode=READ_MODE_BOOL,
        ),
    ),
    "12": tuple(
        [
            OneWireSwitchEntityDescription(
                key=f"PIO.{id}",
                entity_registry_enabled_default=False,
                name=f"PIO {id}",
                read_mode=READ_MODE_BOOL,
            )
            for id in DEVICE_KEYS_A_B
        ]
        + [
            OneWireSwitchEntityDescription(
                key=f"latch.{id}",
                entity_registry_enabled_default=False,
                name=f"Latch {id}",
                read_mode=READ_MODE_BOOL,
            )
            for id in DEVICE_KEYS_A_B
        ]
    ),
    "26": (
        OneWireSwitchEntityDescription(
            key="IAD",
            entity_registry_enabled_default=False,
            entity_category=EntityCategory.CONFIG,
            name="IAD",
            read_mode=READ_MODE_BOOL,
        ),
    ),
    "29": tuple(
        [
            OneWireSwitchEntityDescription(
                key=f"PIO.{id}",
                entity_registry_enabled_default=False,
                name=f"PIO {id}",
                read_mode=READ_MODE_BOOL,
            )
            for id in DEVICE_KEYS_0_7
        ]
        + [
            OneWireSwitchEntityDescription(
                key=f"latch.{id}",
                entity_registry_enabled_default=False,
                name=f"Latch {id}",
                read_mode=READ_MODE_BOOL,
            )
            for id in DEVICE_KEYS_0_7
        ]
    ),
    "3A": tuple(
        OneWireSwitchEntityDescription(
            key=f"PIO.{id}",
            entity_registry_enabled_default=False,
            name=f"PIO {id}",
            read_mode=READ_MODE_BOOL,
        )
        for id in DEVICE_KEYS_A_B
    ),
    "EF": (),  # "HobbyBoard": special
}

# EF sensors are usually hobbyboards specialized sensors.

HOBBYBOARD_EF: dict[str, tuple[OneWireEntityDescription, ...]] = {
    "HB_HUB": tuple(
        OneWireSwitchEntityDescription(
            key=f"hub/branch.{id}",
            entity_registry_enabled_default=False,
            name=f"Hub Branch {id} Enable",
            read_mode=READ_MODE_BOOL,
            entity_category=EntityCategory.CONFIG,
        )
        for id in DEVICE_KEYS_0_3
    ),
    "HB_MOISTURE_METER": tuple(
        [
            OneWireSwitchEntityDescription(
                key=f"moisture/is_leaf.{id}",
                entity_registry_enabled_default=False,
                name=f"Leaf Sensor {id} Enable",
                read_mode=READ_MODE_BOOL,
                entity_category=EntityCategory.CONFIG,
            )
            for id in DEVICE_KEYS_0_3
        ]
        + [
            OneWireSwitchEntityDescription(
                key=f"moisture/is_moisture.{id}",
                entity_registry_enabled_default=False,
                name=f"Moisture Sensor {id} Enable",
                read_mode=READ_MODE_BOOL,
                entity_category=EntityCategory.CONFIG,
            )
            for id in DEVICE_KEYS_0_3
        ]
    ),
}


def get_sensor_types(
    device_sub_type: str,
) -> dict[str, tuple[OneWireEntityDescription, ...]]:
    """Return the proper info array for the device type."""
    if "HobbyBoard" in device_sub_type:
        return HOBBYBOARD_EF
    return DEVICE_SWITCHES


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up 1-Wire platform."""
    onewire_hub = hass.data[DOMAIN][config_entry.entry_id]

    entities = await hass.async_add_executor_job(get_entities, onewire_hub)
    async_add_entities(entities, True)


def get_entities(onewire_hub: OneWireHub) -> list[OneWireSwitch]:
    """Get a list of entities."""
    if not onewire_hub.devices:
        return []

    entities: list[OneWireSwitch] = []

    for device in onewire_hub.devices:
        family = device.family
        device_type = device.type
        device_id = device.id
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
                OneWireSwitch(
                    description=description,
                    device_id=device_id,
                    device_file=device_file,
                    device_info=device_info,
                    name=name,
                    owproxy=onewire_hub.owproxy,
                )
            )

    return entities


class OneWireSwitch(OneWireEntity, SwitchEntity):
    """Implementation of a 1-Wire switch."""

    entity_description: OneWireSwitchEntityDescription

    @property
    def is_on(self) -> bool:
        """Return true if sensor is on."""
        return bool(self._state)

    def turn_on(self, **kwargs: Any) -> None:
        """Turn the entity on."""
        self._write_value(b"1")

    def turn_off(self, **kwargs: Any) -> None:
        """Turn the entity off."""
        self._write_value(b"0")
