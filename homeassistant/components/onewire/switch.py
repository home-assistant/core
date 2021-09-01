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

from .const import CONF_TYPE_OWSERVER, DOMAIN, READ_MODE_BOOL
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
    "12": (
        OneWireSwitchEntityDescription(
            key="PIO.A",
            entity_registry_enabled_default=False,
            name="PIO A",
            read_mode=READ_MODE_BOOL,
        ),
        OneWireSwitchEntityDescription(
            key="PIO.B",
            entity_registry_enabled_default=False,
            name="PIO B",
            read_mode=READ_MODE_BOOL,
        ),
        OneWireSwitchEntityDescription(
            key="latch.A",
            entity_registry_enabled_default=False,
            name="Latch A",
            read_mode=READ_MODE_BOOL,
        ),
        OneWireSwitchEntityDescription(
            key="latch.B",
            entity_registry_enabled_default=False,
            name="Latch B",
            read_mode=READ_MODE_BOOL,
        ),
    ),
    "29": (
        OneWireSwitchEntityDescription(
            key="PIO.0",
            entity_registry_enabled_default=False,
            name="PIO 0",
            read_mode=READ_MODE_BOOL,
        ),
        OneWireSwitchEntityDescription(
            key="PIO.1",
            entity_registry_enabled_default=False,
            name="PIO 1",
            read_mode=READ_MODE_BOOL,
        ),
        OneWireSwitchEntityDescription(
            key="PIO.2",
            entity_registry_enabled_default=False,
            name="PIO 2",
            read_mode=READ_MODE_BOOL,
        ),
        OneWireSwitchEntityDescription(
            key="PIO.3",
            entity_registry_enabled_default=False,
            name="PIO 3",
            read_mode=READ_MODE_BOOL,
        ),
        OneWireSwitchEntityDescription(
            key="PIO.4",
            entity_registry_enabled_default=False,
            name="PIO 4",
            read_mode=READ_MODE_BOOL,
        ),
        OneWireSwitchEntityDescription(
            key="PIO.5",
            entity_registry_enabled_default=False,
            name="PIO 5",
            read_mode=READ_MODE_BOOL,
        ),
        OneWireSwitchEntityDescription(
            key="PIO.6",
            entity_registry_enabled_default=False,
            name="PIO 6",
            read_mode=READ_MODE_BOOL,
        ),
        OneWireSwitchEntityDescription(
            key="PIO.7",
            entity_registry_enabled_default=False,
            name="PIO 7",
            read_mode=READ_MODE_BOOL,
        ),
        OneWireSwitchEntityDescription(
            key="latch.0",
            entity_registry_enabled_default=False,
            name="Latch 0",
            read_mode=READ_MODE_BOOL,
        ),
        OneWireSwitchEntityDescription(
            key="latch.1",
            entity_registry_enabled_default=False,
            name="Latch 1",
            read_mode=READ_MODE_BOOL,
        ),
        OneWireSwitchEntityDescription(
            key="latch.2",
            entity_registry_enabled_default=False,
            name="Latch 2",
            read_mode=READ_MODE_BOOL,
        ),
        OneWireSwitchEntityDescription(
            key="latch.3",
            entity_registry_enabled_default=False,
            name="Latch 3",
            read_mode=READ_MODE_BOOL,
        ),
        OneWireSwitchEntityDescription(
            key="latch.4",
            entity_registry_enabled_default=False,
            name="Latch 4",
            read_mode=READ_MODE_BOOL,
        ),
        OneWireSwitchEntityDescription(
            key="latch.5",
            entity_registry_enabled_default=False,
            name="Latch 5",
            read_mode=READ_MODE_BOOL,
        ),
        OneWireSwitchEntityDescription(
            key="latch.6",
            entity_registry_enabled_default=False,
            name="Latch 6",
            read_mode=READ_MODE_BOOL,
        ),
        OneWireSwitchEntityDescription(
            key="latch.7",
            entity_registry_enabled_default=False,
            name="Latch 7",
            read_mode=READ_MODE_BOOL,
        ),
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
