"""Support for 1-Wire environment switches."""
from __future__ import annotations

from dataclasses import dataclass
import logging
import os
from typing import Any

from homeassistant.components.switch import SwitchEntity, SwitchEntityDescription
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    ATTR_IDENTIFIERS,
    ATTR_MANUFACTURER,
    ATTR_MODEL,
    ATTR_NAME,
    CONF_TYPE,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import (
    CONF_TYPE_OWSERVER,
    DEVICE_KEYS_0_7,
    DEVICE_KEYS_A_B,
    DOMAIN,
    READ_MODE_BOOL,
)
from .onewire_entities import OneWireEntityDescription, OneWireProxyEntity
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
}

LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up 1-Wire platform."""
    # Only OWServer implementation works with switches
    if config_entry.data[CONF_TYPE] == CONF_TYPE_OWSERVER:
        onewirehub = hass.data[DOMAIN][config_entry.entry_id]

        entities = await hass.async_add_executor_job(get_entities, onewirehub)
        async_add_entities(entities, True)


def get_entities(onewirehub: OneWireHub) -> list[SwitchEntity]:
    """Get a list of entities."""
    if not onewirehub.devices:
        return []

    entities: list[SwitchEntity] = []

    for device in onewirehub.devices:
        family = device["family"]
        device_type = device["type"]
        device_id = os.path.split(os.path.split(device["path"])[0])[1]

        if family not in DEVICE_SWITCHES:
            continue

        device_info: DeviceInfo = {
            ATTR_IDENTIFIERS: {(DOMAIN, device_id)},
            ATTR_MANUFACTURER: "Maxim Integrated",
            ATTR_MODEL: device_type,
            ATTR_NAME: device_id,
        }
        for description in DEVICE_SWITCHES[family]:
            device_file = os.path.join(
                os.path.split(device["path"])[0], description.key
            )
            name = f"{device_id} {description.name}"
            entities.append(
                OneWireProxySwitch(
                    description=description,
                    device_id=device_id,
                    device_file=device_file,
                    device_info=device_info,
                    name=name,
                    owproxy=onewirehub.owproxy,
                )
            )

    return entities


class OneWireProxySwitch(OneWireProxyEntity, SwitchEntity):
    """Implementation of a 1-Wire switch."""

    entity_description: OneWireSwitchEntityDescription

    @property
    def is_on(self) -> bool:
        """Return true if sensor is on."""
        return bool(self._state)

    def turn_on(self, **kwargs: Any) -> None:
        """Turn the entity on."""
        self._write_value_ownet(b"1")

    def turn_off(self, **kwargs: Any) -> None:
        """Turn the entity off."""
        self._write_value_ownet(b"0")
