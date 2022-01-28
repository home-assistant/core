"""Support for IKEA Tradfri sensors."""
from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any, cast

from pytradfri.command import Command

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
class TradfriSensorEntityDescription(SensorEntityDescription):
    """Class describing Tradfri sensor entities."""

    value: Callable[[TradfriSensor], Any | None] = None  # type: ignore


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up a Tradfri config entry."""
    gateway_id = config_entry.data[CONF_GATEWAY_ID]
    coordinator_data = hass.data[DOMAIN][config_entry.entry_id][COORDINATOR]
    api = coordinator_data[KEY_API]

    entity_list: list[TradfriSensor] = []

    for device_coordinator in coordinator_data[COORDINATOR_LIST]:
        if (
            not device_coordinator.device.has_light_control
            and not device_coordinator.device.has_socket_control
            and not device_coordinator.device.has_signal_repeater_control
            and not device_coordinator.device.has_air_purifier_control
        ):
            entity_list.append(
                TradfriSensor(
                    device_coordinator,
                    api,
                    gateway_id,
                    description=TradfriSensorEntityDescription(
                        device_class=SensorDeviceClass.BATTERY,
                        native_unit_of_measurement=PERCENTAGE,
                        key=SensorDeviceClass.BATTERY,
                        value=lambda data: cast(
                            int, data.coordinator.data.device_info.battery_level
                        ),
                    ),
                )
            )
        elif device_coordinator.device.has_air_purifier_control:
            entity_list.append(
                TradfriSensor(
                    device_coordinator,
                    api,
                    gateway_id,
                    description=TradfriSensorEntityDescription(
                        device_class=SensorDeviceClass.AQI,
                        native_unit_of_measurement=CONCENTRATION_MICROGRAMS_PER_CUBIC_METER,
                        key=SensorDeviceClass.AQI,
                        # The sensor returns 65535 if the fan is turned off
                        value=lambda data: None
                        if data.coordinator.data.air_purifier_control.air_purifiers[
                            0
                        ].air_quality
                        == 65535
                        else data.coordinator.data.air_purifier_control.air_purifiers[
                            0
                        ].air_quality,
                    ),
                )
            )

    async_add_entities(entity_list)


class TradfriSensor(TradfriBaseEntity, SensorEntity):
    """The platform class required by Home Assistant."""

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

        self._device_description = description

        self._attr_device_class = description.device_class
        self._attr_native_unit_of_measurement = description.native_unit_of_measurement

        self._refresh()  # Set initial state

    def _refresh(self) -> None:
        """Refresh the device."""
        _native_value = self._device_description.value(self)

        self._attr_native_value = _native_value
