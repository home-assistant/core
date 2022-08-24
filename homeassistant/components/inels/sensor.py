"""Inelse sensor entity."""
from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from operator import itemgetter
from typing import Any

from inelsmqtt.const import BATTERY, RFTI_10B, TEMP_IN, TEMP_OUT, TEMP_SENSOR_DATA
from inelsmqtt.devices import Device

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import PERCENTAGE, TEMP_CELSIUS, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .base_class import InelsBaseEntity
from .const import COORDINATOR_LIST, DOMAIN, ICON_BATTERY, ICON_TEMPERATURE
from .coordinator import InelsDeviceUpdateCoordinator


@dataclass
class InelsSensorEntityDescriptionMixin:
    """Mixin keys."""

    value: Callable[[Device], Any | None]


@dataclass
class InelsSensorEntityDescription(
    SensorEntityDescription, InelsSensorEntityDescriptionMixin
):
    """Class for describing inels entities."""


def _process_data(data: str, indexes: list) -> str:
    """Process data for specific type of measurements."""
    array = data.split("\n")[:-1]
    data_range = itemgetter(*indexes)(array)
    range_joined = "".join(data_range)

    return f"0x{range_joined}"


def __get_battery_level(device: Device) -> int | None:
    """Get battery level of the device."""
    if device.is_available is False:
        return None

    # then get calculate the battery. In our case iss 100 or 0
    return (
        100
        if int(_process_data(device.state, TEMP_SENSOR_DATA[BATTERY]), 16) == 0
        else 0
    )


def __get_temperature_in(device: Device) -> float | None:
    """Get temperature inside."""
    if device.is_available is False:
        return None

    return int(_process_data(device.state, TEMP_SENSOR_DATA[TEMP_IN]), 16) / 100


def __get_temperature_out(device: Device) -> float | None:
    """Get temperature outside."""
    if device.is_available is False:
        return None

    return int(_process_data(device.state, TEMP_SENSOR_DATA[TEMP_OUT]), 16) / 100


SENSOR_DESCRIPTION_TEMPERATURE: tuple[InelsSensorEntityDescription, ...] = (
    InelsSensorEntityDescription(
        key="battery_level",
        name="Battery",
        device_class=SensorDeviceClass.BATTERY,
        icon=ICON_BATTERY,
        native_unit_of_measurement=PERCENTAGE,
        value=__get_battery_level,
    ),
    InelsSensorEntityDescription(
        key="temp_in",
        name="Temperature In",
        device_class=SensorDeviceClass.TEMPERATURE,
        icon=ICON_TEMPERATURE,
        native_unit_of_measurement=TEMP_CELSIUS,
        value=__get_temperature_in,
    ),
    InelsSensorEntityDescription(
        key="temp_out",
        name="Temperature Out",
        device_class=SensorDeviceClass.TEMPERATURE,
        icon=ICON_TEMPERATURE,
        native_unit_of_measurement=TEMP_CELSIUS,
        value=__get_temperature_out,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Load Inels switch.."""
    coordinator_data: list[InelsDeviceUpdateCoordinator] = hass.data[DOMAIN][
        config_entry.entry_id
    ][COORDINATOR_LIST]

    entities: list[InelsSensor] = []

    for device_coordinator in coordinator_data:
        if device_coordinator.device.device_type == Platform.SENSOR:
            if device_coordinator.device.inels_type == RFTI_10B:
                descriptions = SENSOR_DESCRIPTION_TEMPERATURE
            else:
                continue

            for description in descriptions:
                entities.append(
                    InelsSensor(device_coordinator, description=description)
                )

    async_add_entities(entities, True)


class InelsSensor(InelsBaseEntity, SensorEntity):
    """The platform class required by Home Assistant."""

    entity_description: InelsSensorEntityDescription

    def __init__(
        self,
        device_coordinator: InelsDeviceUpdateCoordinator,
        description: InelsSensorEntityDescription,
    ) -> None:
        """Initialize a sensor."""
        super().__init__(device_coordinator=device_coordinator)

        self._device_control = self._device

        self.entity_description = description
        self._attr_unique_id = f"{self._attr_unique_id}-{description.key}"

        if description.name:
            self._attr_name = f"{self._attr_name}-{description.name}"

    def _refresh(self) -> None:
        """Refresh the device."""
        super()._refresh()
        self._device_control = self._device
        self._attr_native_value = self.entity_description.value(self._device_control)
