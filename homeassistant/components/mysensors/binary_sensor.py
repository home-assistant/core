"""Support for MySensors binary sensors."""
from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .. import mysensors
from .const import MYSENSORS_DISCOVERY, DiscoveryInfo
from .helpers import on_unload


@dataclass(frozen=True)
class MySensorsBinarySensorDescription(BinarySensorEntityDescription):
    """Describe a MySensors binary sensor entity."""

    is_on: Callable[[int, dict[int, str]], bool] = (
        lambda value_type, values: values[value_type] == "1"
    )


SENSORS: dict[str, MySensorsBinarySensorDescription] = {
    "S_DOOR": MySensorsBinarySensorDescription(
        key="S_DOOR",
        device_class=BinarySensorDeviceClass.DOOR,
    ),
    "S_MOTION": MySensorsBinarySensorDescription(
        key="S_MOTION",
        device_class=BinarySensorDeviceClass.MOTION,
    ),
    "S_SMOKE": MySensorsBinarySensorDescription(
        key="S_SMOKE",
        device_class=BinarySensorDeviceClass.SMOKE,
    ),
    "S_SPRINKLER": MySensorsBinarySensorDescription(
        key="S_SPRINKLER",
        device_class=BinarySensorDeviceClass.SAFETY,
    ),
    "S_WATER_LEAK": MySensorsBinarySensorDescription(
        key="S_WATER_LEAK",
        device_class=BinarySensorDeviceClass.SAFETY,
    ),
    "S_SOUND": MySensorsBinarySensorDescription(
        key="S_SOUND",
        device_class=BinarySensorDeviceClass.SOUND,
    ),
    "S_VIBRATION": MySensorsBinarySensorDescription(
        key="S_VIBRATION",
        device_class=BinarySensorDeviceClass.VIBRATION,
    ),
    "S_MOISTURE": MySensorsBinarySensorDescription(
        key="S_MOISTURE",
        device_class=BinarySensorDeviceClass.MOISTURE,
    ),
}


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up this platform for a specific ConfigEntry(==Gateway)."""

    @callback
    def async_discover(discovery_info: DiscoveryInfo) -> None:
        """Discover and add a MySensors binary_sensor."""
        mysensors.setup_mysensors_platform(
            hass,
            Platform.BINARY_SENSOR,
            discovery_info,
            MySensorsBinarySensor,
            async_add_entities=async_add_entities,
        )

    on_unload(
        hass,
        config_entry.entry_id,
        async_dispatcher_connect(
            hass,
            MYSENSORS_DISCOVERY.format(config_entry.entry_id, Platform.BINARY_SENSOR),
            async_discover,
        ),
    )


class MySensorsBinarySensor(mysensors.device.MySensorsChildEntity, BinarySensorEntity):
    """Representation of a MySensors binary sensor child node."""

    entity_description: MySensorsBinarySensorDescription

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        """Set up the instance."""
        super().__init__(*args, **kwargs)
        pres = self.gateway.const.Presentation
        self.entity_description = SENSORS[pres(self.child_type).name]

    @property
    def is_on(self) -> bool:
        """Return True if the binary sensor is on."""
        return self.entity_description.is_on(self.value_type, self._child.values)
