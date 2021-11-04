"""Support for Velbus sensors."""
from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Final

from velbusaio.channels import Channel as VelbusChannel

from homeassistant.components.sensor import (
    STATE_CLASS_MEASUREMENT,
    STATE_CLASS_TOTAL_INCREASING,
    SensorEntity,
    SensorEntityDescription,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import DEVICE_CLASS_POWER, DEVICE_CLASS_TEMPERATURE
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import VelbusEntity, VelbusEntityDescriptionMixin
from .const import DOMAIN


@dataclass
class VelbusSensorEntityDescriptionMixin(VelbusEntityDescriptionMixin):
    """Bases description for Velbus Sensor entities."""

    native_value: Callable[[VelbusChannel], float | int | None]


@dataclass
class VelbusSensorEntityDescription(
    SensorEntityDescription, VelbusSensorEntityDescriptionMixin
):
    """Base velbus sensor entitydescription."""


SENSOR_TYPES: Final[tuple[VelbusSensorEntityDescription, ...]] = (
    VelbusSensorEntityDescription(
        key="",
        state_class=STATE_CLASS_MEASUREMENT,
        suitable=lambda channel: not channel.is_temperature(),
        native_value=lambda channel: channel.get_state(),
    ),
    VelbusSensorEntityDescription(
        key="",
        device_class=DEVICE_CLASS_TEMPERATURE,
        state_class=STATE_CLASS_MEASUREMENT,
        suitable=lambda channel: channel.is_temperature(),
        native_value=lambda channel: channel.get_state(),
    ),
    VelbusSensorEntityDescription(
        name="max",
        key="max",
        device_class=DEVICE_CLASS_TEMPERATURE,
        state_class=STATE_CLASS_MEASUREMENT,
        suitable=lambda channel: channel.is_temperature(),
        native_value=lambda channel: channel.get_max(),
        entity_registry_enabled_default=False,
    ),
    VelbusSensorEntityDescription(
        name="min",
        key="min",
        device_class=DEVICE_CLASS_TEMPERATURE,
        state_class=STATE_CLASS_MEASUREMENT,
        suitable=lambda channel: channel.is_temperature(),
        native_value=lambda channel: channel.get_min(),
        entity_registry_enabled_default=False,
    ),
    VelbusSensorEntityDescription(
        name="counter",
        key="counter",
        device_class=DEVICE_CLASS_POWER,
        state_class=STATE_CLASS_TOTAL_INCREASING,
        suitable=lambda channel: channel.is_counter_channel(),
        native_value=lambda channel: channel.get_counter_state(),
        icon="mdi:counter",
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Velbus switch based on config_entry."""
    await hass.data[DOMAIN][entry.entry_id]["tsk"]
    cntrl = hass.data[DOMAIN][entry.entry_id]["cntrl"]
    entities = []
    for channel in cntrl.get_all("sensor"):
        for description in SENSOR_TYPES:
            if description.suitable(channel):
                entities.append(VelbusSensor(channel, description))
    async_add_entities(entities)


class VelbusSensor(VelbusEntity, SensorEntity):
    """The entity class for FRITZ!SmartHome sensors."""

    entity_description: VelbusSensorEntityDescription

    def __init__(
        self, channel: VelbusChannel, description: VelbusSensorEntityDescription
    ) -> None:
        """Initialize the dimmer."""
        super().__init__(channel, description)
        self._attr_native_unit_of_measurement = self._channel.get_unit()

    @property
    def native_value(self) -> float | int | None:
        """Return the state of the sensor."""
        return self.entity_description.native_value(self._channel)
