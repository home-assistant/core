"""Support for Fritzbox binary sensors."""
from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Final

from pyfritzhome.fritzhomedevice import FritzhomeDevice

from homeassistant.components.binary_sensor import (
    DEVICE_CLASS_WINDOW,
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from . import FritzBoxEntity
from .const import CONF_COORDINATOR, DOMAIN as FRITZBOX_DOMAIN
from .model import FritzEntityDescriptionMixinBase


@dataclass
class FritzEntityDescriptionMixinBinarySensor(FritzEntityDescriptionMixinBase):
    """BinarySensor description mixin for Fritz!Smarthome entities."""

    is_on: Callable[[FritzhomeDevice], bool | None]


@dataclass
class FritzBinarySensorEntityDescription(
    BinarySensorEntityDescription, FritzEntityDescriptionMixinBinarySensor
):
    """Description for Fritz!Smarthome binary sensor entities."""


BINARY_SENSOR_TYPES: Final[tuple[FritzBinarySensorEntityDescription, ...]] = (
    FritzBinarySensorEntityDescription(
        key="alarm",
        name="Alarm",
        device_class=DEVICE_CLASS_WINDOW,
        suitable=lambda device: device.has_alarm,  # type: ignore[no-any-return]
        is_on=lambda device: device.alert_state,  # type: ignore[no-any-return]
    ),
)


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up the FRITZ!SmartHome binary sensor from ConfigEntry."""
    coordinator = hass.data[FRITZBOX_DOMAIN][entry.entry_id][CONF_COORDINATOR]

    async_add_entities(
        [
            FritzboxBinarySensor(coordinator, ain, description)
            for ain, device in coordinator.data.items()
            for description in BINARY_SENSOR_TYPES
            if description.suitable(device)
        ]
    )


class FritzboxBinarySensor(FritzBoxEntity, BinarySensorEntity):
    """Representation of a binary FRITZ!SmartHome device."""

    entity_description: FritzBinarySensorEntityDescription

    def __init__(
        self,
        coordinator: DataUpdateCoordinator[dict[str, FritzhomeDevice]],
        ain: str,
        entity_description: FritzBinarySensorEntityDescription,
    ) -> None:
        """Initialize the FritzBox entity."""
        super().__init__(coordinator, ain, entity_description)
        self._attr_name = self.device.name
        self._attr_unique_id = ain

    @property
    def is_on(self) -> bool | None:
        """Return true if sensor is on."""
        return self.entity_description.is_on(self.device)
