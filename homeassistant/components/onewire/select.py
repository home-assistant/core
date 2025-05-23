"""Support for 1-Wire environment select entities."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta
import os

from homeassistant.components.select import SelectEntity, SelectEntityDescription
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import READ_MODE_INT
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
class OneWireSelectEntityDescription(OneWireEntityDescription, SelectEntityDescription):
    """Class describing OneWire select entities."""


ENTITY_DESCRIPTIONS: dict[str, tuple[OneWireEntityDescription, ...]] = {
    "28": (
        OneWireSelectEntityDescription(
            key="tempres",
            entity_category=EntityCategory.CONFIG,
            read_mode=READ_MODE_INT,
            options=["9", "10", "11", "12"],
            translation_key="tempres",
        ),
    ),
}


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: OneWireConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
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
) -> list[OneWireSelectEntity]:
    """Get a list of entities."""
    entities: list[OneWireSelectEntity] = []

    for device in devices:
        family = device.family
        device_id = device.id
        device_info = device.device_info

        if family not in ENTITY_DESCRIPTIONS:
            continue
        for description in ENTITY_DESCRIPTIONS[family]:
            device_file = os.path.join(os.path.split(device.path)[0], description.key)
            entities.append(
                OneWireSelectEntity(
                    description=description,
                    device_id=device_id,
                    device_file=device_file,
                    device_info=device_info,
                    owproxy=onewire_hub.owproxy,
                )
            )

    return entities


class OneWireSelectEntity(OneWireEntity, SelectEntity):
    """Implementation of a 1-Wire switch."""

    entity_description: OneWireSelectEntityDescription

    @property
    def current_option(self) -> str | None:
        """Return the selected entity option to represent the entity state."""
        return str(self._state)

    def select_option(self, option: str) -> None:
        """Change the selected option."""
        self._write_value(option.encode("ascii"))
