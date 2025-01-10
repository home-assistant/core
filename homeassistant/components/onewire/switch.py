"""Support for 1-Wire environment switches."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta
import os
from typing import Any

from homeassistant.components.switch import SwitchEntity, SwitchEntityDescription
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DEVICE_KEYS_0_3, DEVICE_KEYS_0_7, DEVICE_KEYS_A_B, READ_MODE_BOOL
from .entity import OneWireEntity, OneWireEntityDescription
from .onewirehub import (
    SIGNAL_NEW_DEVICE_CONNECTED,
    OneWireConfigEntry,
    OneWireHub,
    OWDeviceDescription,
)

# the library uses non-persistent connections
# and concurrent access to the bus is managed by the server
PARALLEL_UPDATES = 0
SCAN_INTERVAL = timedelta(seconds=30)


@dataclass(frozen=True)
class OneWireSwitchEntityDescription(OneWireEntityDescription, SwitchEntityDescription):
    """Class describing OneWire switch entities."""


DEVICE_SWITCHES: dict[str, tuple[OneWireEntityDescription, ...]] = {
    "05": (
        OneWireSwitchEntityDescription(
            key="PIO",
            entity_registry_enabled_default=False,
            read_mode=READ_MODE_BOOL,
            translation_key="pio",
        ),
    ),
    "12": tuple(
        [
            OneWireSwitchEntityDescription(
                key=f"PIO.{device_key}",
                entity_registry_enabled_default=False,
                read_mode=READ_MODE_BOOL,
                translation_key="pio_id",
                translation_placeholders={"id": str(device_key)},
            )
            for device_key in DEVICE_KEYS_A_B
        ]
        + [
            OneWireSwitchEntityDescription(
                key=f"latch.{device_key}",
                entity_registry_enabled_default=False,
                read_mode=READ_MODE_BOOL,
                translation_key="latch_id",
                translation_placeholders={"id": str(device_key)},
            )
            for device_key in DEVICE_KEYS_A_B
        ]
    ),
    "26": (
        OneWireSwitchEntityDescription(
            key="IAD",
            entity_registry_enabled_default=False,
            entity_category=EntityCategory.CONFIG,
            read_mode=READ_MODE_BOOL,
            translation_key="iad",
        ),
    ),
    "29": tuple(
        [
            OneWireSwitchEntityDescription(
                key=f"PIO.{device_key}",
                entity_registry_enabled_default=False,
                read_mode=READ_MODE_BOOL,
                translation_key="pio_id",
                translation_placeholders={"id": str(device_key)},
            )
            for device_key in DEVICE_KEYS_0_7
        ]
        + [
            OneWireSwitchEntityDescription(
                key=f"latch.{device_key}",
                entity_registry_enabled_default=False,
                read_mode=READ_MODE_BOOL,
                translation_key="latch_id",
                translation_placeholders={"id": str(device_key)},
            )
            for device_key in DEVICE_KEYS_0_7
        ]
    ),
    "3A": tuple(
        OneWireSwitchEntityDescription(
            key=f"PIO.{device_key}",
            entity_registry_enabled_default=False,
            read_mode=READ_MODE_BOOL,
            translation_key="pio_id",
            translation_placeholders={"id": str(device_key)},
        )
        for device_key in DEVICE_KEYS_A_B
    ),
    "EF": (),  # "HobbyBoard": special
}

# EF sensors are usually hobbyboards specialized sensors.

HOBBYBOARD_EF: dict[str, tuple[OneWireEntityDescription, ...]] = {
    "HB_HUB": tuple(
        OneWireSwitchEntityDescription(
            key=f"hub/branch.{device_key}",
            entity_registry_enabled_default=False,
            read_mode=READ_MODE_BOOL,
            entity_category=EntityCategory.CONFIG,
            translation_key="hub_branch_id",
            translation_placeholders={"id": str(device_key)},
        )
        for device_key in DEVICE_KEYS_0_3
    ),
    "HB_MOISTURE_METER": tuple(
        [
            OneWireSwitchEntityDescription(
                key=f"moisture/is_leaf.{device_key}",
                entity_registry_enabled_default=False,
                read_mode=READ_MODE_BOOL,
                entity_category=EntityCategory.CONFIG,
                translation_key="leaf_sensor_id",
                translation_placeholders={"id": str(device_key)},
            )
            for device_key in DEVICE_KEYS_0_3
        ]
        + [
            OneWireSwitchEntityDescription(
                key=f"moisture/is_moisture.{device_key}",
                entity_registry_enabled_default=False,
                read_mode=READ_MODE_BOOL,
                entity_category=EntityCategory.CONFIG,
                translation_key="moisture_sensor_id",
                translation_placeholders={"id": str(device_key)},
            )
            for device_key in DEVICE_KEYS_0_3
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
    config_entry: OneWireConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up 1-Wire platform."""

    async def _add_entities(
        hub: OneWireHub, devices: list[OWDeviceDescription]
    ) -> None:
        """Add 1-Wire entities for all devices."""
        if not devices:
            return
        async_add_entities(get_entities(hub, devices), True)

    hub = config_entry.runtime_data
    await _add_entities(hub, hub.devices)
    config_entry.async_on_unload(
        async_dispatcher_connect(hass, SIGNAL_NEW_DEVICE_CONNECTED, _add_entities)
    )


def get_entities(
    onewire_hub: OneWireHub, devices: list[OWDeviceDescription]
) -> list[OneWireSwitch]:
    """Get a list of entities."""
    entities: list[OneWireSwitch] = []

    for device in devices:
        family = device.family
        device_type = device.type
        device_id = device.id
        device_info = device.device_info
        device_sub_type = "std"
        if device_type and "EF" in family:
            device_sub_type = "HobbyBoard"
            family = device_type
        elif "A6" in family:
            # A6 is a secondary family code for DS2438
            family = "26"

        if family not in get_sensor_types(device_sub_type):
            continue
        for description in get_sensor_types(device_sub_type)[family]:
            device_file = os.path.join(os.path.split(device.path)[0], description.key)
            entities.append(
                OneWireSwitch(
                    description=description,
                    device_id=device_id,
                    device_file=device_file,
                    device_info=device_info,
                    owproxy=onewire_hub.owproxy,
                )
            )

    return entities


class OneWireSwitch(OneWireEntity, SwitchEntity):
    """Implementation of a 1-Wire switch."""

    entity_description: OneWireSwitchEntityDescription

    @property
    def is_on(self) -> bool | None:
        """Return true if switch is on."""
        if self._state is None:
            return None
        return bool(self._state)

    def turn_on(self, **kwargs: Any) -> None:
        """Turn the entity on."""
        self._write_value(b"1")

    def turn_off(self, **kwargs: Any) -> None:
        """Turn the entity off."""
        self._write_value(b"0")
