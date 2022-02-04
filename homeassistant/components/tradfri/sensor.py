"""Support for IKEA Tradfri sensors."""
from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any, cast

from pytradfri.command import Command
from pytradfri.device import Device

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONCENTRATION_MICROGRAMS_PER_CUBIC_METER, PERCENTAGE
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .base_class import TradfriBaseEntity
from .const import CONF_GATEWAY_ID, COORDINATOR, COORDINATOR_LIST, DOMAIN, KEY_API
from .coordinator import TradfriDeviceDataUpdateCoordinator


@dataclass
class TradfriSensorEntityDescriptionMixin:
    """Mixin for required keys."""

    value: Callable[[Device], Any | None]


@dataclass
class TradfriSensorEntityDescription(
    SensorEntityDescription,
    TradfriSensorEntityDescriptionMixin,
):
    """Class describing Tradfri sensor entities."""


def _get_air_quality(device: Device) -> int | None:
    """Fetch the air quality value."""
    if (
        device.air_purifier_control.air_purifiers[0].air_quality == 65535
    ):  # The sensor returns 65535 if the fan is turned off
        return None

    return cast(int, device.air_purifier_control.air_purifiers[0].air_quality)


SENSOR_DESCRIPTION_AQI = TradfriSensorEntityDescription(
    device_class=SensorDeviceClass.AQI,
    native_unit_of_measurement=CONCENTRATION_MICROGRAMS_PER_CUBIC_METER,
    key=SensorDeviceClass.AQI,
    value=_get_air_quality,
)

SENSOR_DESCRIPTION_BATTERY = TradfriSensorEntityDescription(
    device_class=SensorDeviceClass.BATTERY,
    native_unit_of_measurement=PERCENTAGE,
    key=SensorDeviceClass.BATTERY,
    value=lambda device: cast(int, device.device_info.battery_level),
)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up a Tradfri config entry."""
    gateway_id = config_entry.data[CONF_GATEWAY_ID]
    coordinator_data = hass.data[DOMAIN][config_entry.entry_id][COORDINATOR]
    api = coordinator_data[KEY_API]

    entities: list[TradfriSensor] = []

    for device_coordinator in coordinator_data[COORDINATOR_LIST]:
        description = None
        if (
            not device_coordinator.device.has_light_control
            and not device_coordinator.device.has_socket_control
            and not device_coordinator.device.has_signal_repeater_control
            and not device_coordinator.device.has_air_purifier_control
        ):
            description = SENSOR_DESCRIPTION_BATTERY
        elif device_coordinator.device.has_air_purifier_control:
            description = SENSOR_DESCRIPTION_AQI

        if description:
            entities.append(
                TradfriSensor(
                    device_coordinator,
                    api,
                    gateway_id,
                    description=description,
                )
            )

    async_add_entities(entities)


class TradfriSensor(TradfriBaseEntity, SensorEntity):
    """The platform class required by Home Assistant."""

    entity_description: TradfriSensorEntityDescription

    def __init__(
        self,
        device_coordinator: TradfriDeviceDataUpdateCoordinator,
        api: Callable[[Command | list[Command]], Any],
        gateway_id: str,
        description: TradfriSensorEntityDescription,
    ) -> None:
        """Initialize a Tradfri sensor."""
        super().__init__(
            device_coordinator=device_coordinator,
            api=api,
            gateway_id=gateway_id,
        )

        self.entity_description = description

        self._refresh()  # Set initial state

    def _refresh(self) -> None:
        """Refresh the device."""
        self._attr_native_value = self.entity_description.value(self.coordinator.data)
