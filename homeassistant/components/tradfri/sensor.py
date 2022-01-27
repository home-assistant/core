"""Support for IKEA Tradfri sensors."""
from __future__ import annotations

from collections.abc import Callable
from typing import Any

from pytradfri.command import Command

from homeassistant.components.sensor import SensorDeviceClass, SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONCENTRATION_MICROGRAMS_PER_CUBIC_METER, PERCENTAGE
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .base_class import TradfriBaseEntity
from .const import CONF_GATEWAY_ID, COORDINATOR, COORDINATOR_LIST, DOMAIN, KEY_API
from .coordinator import TradfriDeviceDataUpdateCoordinator


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up a Tradfri config entry."""
    gateway_id = config_entry.data[CONF_GATEWAY_ID]
    coordinator_data = hass.data[DOMAIN][config_entry.entry_id][COORDINATOR]
    api = coordinator_data[KEY_API]

    entities: list[TradfriBaseEntity] = [
        TradfriBatterySensor(
            device_coordinator,
            api,
            gateway_id,
        )
        for device_coordinator in coordinator_data[COORDINATOR_LIST]
        if (
            not device_coordinator.device.has_light_control
            and not device_coordinator.device.has_socket_control
            and not device_coordinator.device.has_signal_repeater_control
            and not device_coordinator.device.has_air_purifier_control
        )
    ]

    entities.extend(
        [
            AirQualitySensor(
                device_coordinator,
                api,
                gateway_id,
            )
            for device_coordinator in coordinator_data[COORDINATOR_LIST]
            if device_coordinator.device.has_air_purifier_control
        ]
    )

    async_add_entities(entities)


class TradfriBatterySensor(TradfriBaseEntity, SensorEntity):
    """The platform class required by Home Assistant."""

    _attr_device_class = SensorDeviceClass.BATTERY
    _attr_native_unit_of_measurement = PERCENTAGE

    def __init__(
        self,
        device_coordinator: TradfriDeviceDataUpdateCoordinator,
        api: Callable[[Command | list[Command]], Any],
        gateway_id: str,
    ) -> None:
        """Initialize a battery sensor."""
        super().__init__(
            device_coordinator=device_coordinator,
            api=api,
            gateway_id=gateway_id,
        )

        self._refresh()  # Set initial state

    def _refresh(self) -> None:
        """Refresh the device."""
        self._attr_native_value = self.coordinator.data.device_info.battery_level


class AirQualitySensor(TradfriBaseEntity, SensorEntity):
    """
    The platform class required by Home Assistant.

    Following the discussion here, the sensor seem to be reporting in microgram per
    m3:
    https://github.com/dresden-elektronik/deconz-rest-plugin/
    issues/5351#issuecomment-968362604
    """

    _attr_device_class = SensorDeviceClass.AQI
    _attr_native_unit_of_measurement = CONCENTRATION_MICROGRAMS_PER_CUBIC_METER

    def __init__(
        self,
        device_coordinator: TradfriDeviceDataUpdateCoordinator,
        api: Callable[[Command | list[Command]], Any],
        gateway_id: str,
    ) -> None:
        """Initialize a air quality sensor."""
        super().__init__(
            device_coordinator=device_coordinator,
            api=api,
            gateway_id=gateway_id,
        )

        self._refresh()  # Set initial state

        self._attr_unique_id = f"{self._attr_unique_id}-air_quality"

    def _refresh(self) -> None:
        """Refresh the device."""
        aqi_value = self.coordinator.data.air_purifier_control.air_purifiers[
            0
        ].air_quality

        # The sensor has this value if the device is turned off
        if aqi_value == 65535:
            aqi_value = None

        self._attr_native_value = aqi_value
