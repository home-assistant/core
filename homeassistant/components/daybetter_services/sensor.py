"""Sensor platform for DayBetter temperature & humidity."""

from __future__ import annotations

from typing import Any

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import PERCENTAGE, UnitOfTemperature
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import DayBetterCoordinator


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up DayBetter sensors from a config entry."""
    entry_data = hass.data[DOMAIN][entry.entry_id]
    coordinator: DayBetterCoordinator = entry_data["coordinator"]
    devices = coordinator.data or []

    entities: list[SensorEntity] = []
    for device in devices:
        if device.get("type") != 5:
            continue

        device_name = device.get("deviceName", "unknown")
        device_id = device.get("deviceId", device_name)
        group = (
            str(device.get("deviceGroupName", device_name)).lower().replace(" ", "_")
        )

        if "temp" in device:
            entities.append(
                DayBetterTemperatureSensor(coordinator, device, device_id, group)
            )

        if "humi" in device:
            entities.append(
                DayBetterHumiditySensor(coordinator, device, device_id, group)
            )

        if "battery" in device:
            entities.append(
                DayBetterBatterySensor(coordinator, device, device_id, group)
            )

    async_add_entities(entities)


class DayBetterSensorBase(CoordinatorEntity[DayBetterCoordinator], SensorEntity):
    """Base class for DayBetter sensors."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: DayBetterCoordinator,
        device: dict[str, Any],
        device_id: int | str,
        group_name: str,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        self._device_name = device.get("deviceName", "unknown")
        self._device_id = device_id
        self._group_name = group_name

    @property
    def device_info(self) -> dr.DeviceInfo:
        """Return device information."""
        device = self._get_device()
        return dr.DeviceInfo(
            identifiers={(DOMAIN, str(self._device_id))},
            name=device.get("deviceGroupName", self._device_name)
            if device
            else self._device_name,
            manufacturer="DayBetter",
            model=device.get("deviceClass", "Sensor") if device else "Sensor",
        )

    def _get_device(self) -> dict[str, Any] | None:
        """Get current device data from coordinator."""
        if not isinstance(self.coordinator.data, list):
            return None

        for device in self.coordinator.data:
            if (
                isinstance(device, dict)
                and device.get("deviceName") == self._device_name
            ):
                return device

        return None


class DayBetterTemperatureSensor(DayBetterSensorBase):
    """Temperature sensor entity."""

    _attr_device_class = SensorDeviceClass.TEMPERATURE
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_native_unit_of_measurement = UnitOfTemperature.CELSIUS

    def __init__(
        self,
        coordinator: DayBetterCoordinator,
        device: dict[str, Any],
        device_id: int | str,
        group_name: str,
    ) -> None:
        """Initialize temperature sensor."""
        super().__init__(coordinator, device, device_id, group_name)
        self._attr_unique_id = f"{device_id}_temperature"
        self._attr_name = "Temperature"

    @property
    def native_value(self) -> float | None:
        """Return the temperature value."""
        device = self._get_device()
        if not device:
            return None

        temp_raw = device.get("temp") or device.get("temperature")
        if temp_raw is None:
            return None

        try:
            return int(temp_raw) / 10.0
        except (TypeError, ValueError):
            return None


class DayBetterHumiditySensor(DayBetterSensorBase):
    """Humidity sensor entity."""

    _attr_device_class = SensorDeviceClass.HUMIDITY
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_native_unit_of_measurement = PERCENTAGE

    def __init__(
        self,
        coordinator: DayBetterCoordinator,
        device: dict[str, Any],
        device_id: int | str,
        group_name: str,
    ) -> None:
        """Initialize humidity sensor."""
        super().__init__(coordinator, device, device_id, group_name)
        self._attr_unique_id = f"{device_id}_humidity"
        self._attr_name = "Humidity"

    @property
    def native_value(self) -> float | None:
        """Return the humidity value."""
        device = self._get_device()
        if not device:
            return None

        humi_raw = device.get("humi") or device.get("humidity")
        if humi_raw is None:
            return None

        try:
            return int(humi_raw) / 10.0
        except (TypeError, ValueError):
            return None


class DayBetterBatterySensor(DayBetterSensorBase):
    """Battery sensor entity."""

    _attr_device_class = SensorDeviceClass.BATTERY
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_native_unit_of_measurement = PERCENTAGE

    def __init__(
        self,
        coordinator: DayBetterCoordinator,
        device: dict[str, Any],
        device_id: int | str,
        group_name: str,
    ) -> None:
        """Initialize battery sensor."""
        super().__init__(coordinator, device, device_id, group_name)
        self._attr_unique_id = f"{device_id}_battery"
        self._attr_name = "Battery"

    @property
    def native_value(self) -> int | None:
        """Return the battery value."""
        device = self._get_device()
        if not device:
            return None

        battery = device.get("battery")
        if battery is None:
            return None

        try:
            return int(battery)
        except (TypeError, ValueError):
            return None
