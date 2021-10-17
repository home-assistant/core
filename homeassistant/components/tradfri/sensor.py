"""Support for IKEA Tradfri sensors."""
from __future__ import annotations

from collections.abc import Callable
from typing import Any, cast

from pytradfri.command import Command

from homeassistant.components.sensor import SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import DEVICE_CLASS_BATTERY, PERCENTAGE
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .base_class import TradfriBaseDevice
from .const import CONF_GATEWAY_ID, DEVICES, DOMAIN, KEY_API


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up a Tradfri config entry."""
    gateway_id = config_entry.data[CONF_GATEWAY_ID]
    tradfri_data = hass.data[DOMAIN][config_entry.entry_id]
    api = tradfri_data[KEY_API]
    devices = tradfri_data[DEVICES]

    sensors = (
        dev
        for dev in devices
        if not dev.has_light_control
        and not dev.has_socket_control
        and not dev.has_blind_control
        and not dev.has_signal_repeater_control
    )
    if sensors:
        async_add_entities(TradfriSensor(sensor, api, gateway_id) for sensor in sensors)


class TradfriSensor(TradfriBaseDevice, SensorEntity):
    """The platform class required by Home Assistant."""

    _attr_device_class = DEVICE_CLASS_BATTERY
    _attr_native_unit_of_measurement = PERCENTAGE

    def __init__(
        self,
        device: Command,
        api: Callable[[Command | list[Command]], Any],
        gateway_id: str,
    ) -> None:
        """Initialize the device."""
        super().__init__(device, api, gateway_id)
        self._attr_unique_id = f"{gateway_id}-{device.id}"

    @property
    def native_value(self) -> int | None:
        """Return the current state of the device."""
        if not self._device:
            return None
        return cast(int, self._device.device_info.battery_level)
