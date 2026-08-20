"""Sensor platform for Marstek devices."""

from __future__ import annotations

import asyncio
from datetime import timedelta
import logging
from typing import Any

from aiomarstek import MarstekUDPClient

from homeassistant.components.sensor import SensorEntity, SensorStateClass
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    PERCENTAGE,
    UnitOfElectricCurrent,
    UnitOfElectricPotential,
    UnitOfPower,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import (
    CoordinatorEntity,
    DataUpdateCoordinator,
)

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

# Update interval for polling device data
SCAN_INTERVAL = timedelta(seconds=10)


def _default_status_data(
    device_ip: str, current_data: dict[str, Any]
) -> dict[str, Any]:
    """Return status data with defaults that preserve previous values."""
    return {
        "battery_soc": current_data.get("battery_soc", 0),
        "battery_power": current_data.get("battery_power", 0),
        "device_mode": current_data.get("device_mode", "Unknown"),
        "battery_status": current_data.get("battery_status", "Unknown"),
        "device_ip": device_ip,
        "last_update": asyncio.get_running_loop().time(),
        "pv1_power": current_data.get("pv1_power", 0),
        "pv1_voltage": current_data.get("pv1_voltage", 0),
        "pv1_current": current_data.get("pv1_current", 0),
        "pv1_state": current_data.get("pv1_state", 0),
        "pv2_power": current_data.get("pv2_power", 0),
        "pv2_voltage": current_data.get("pv2_voltage", 0),
        "pv2_current": current_data.get("pv2_current", 0),
        "pv2_state": current_data.get("pv2_state", 0),
        "pv3_power": current_data.get("pv3_power", 0),
        "pv3_voltage": current_data.get("pv3_voltage", 0),
        "pv3_current": current_data.get("pv3_current", 0),
        "pv3_state": current_data.get("pv3_state", 0),
        "pv4_power": current_data.get("pv4_power", 0),
        "pv4_voltage": current_data.get("pv4_voltage", 0),
        "pv4_current": current_data.get("pv4_current", 0),
        "pv4_state": current_data.get("pv4_state", 0),
    }


class MarstekDataUpdateCoordinator(DataUpdateCoordinator):
    """Per-device data update coordinator."""

    def __init__(
        self, hass: HomeAssistant, udp_client: MarstekUDPClient, device_ip: str
    ) -> None:
        """Initialize the coordinator."""
        self.udp_client = udp_client
        self.device_ip = device_ip
        super().__init__(
            hass,
            _LOGGER,
            name=f"Marstek {device_ip}",
            update_interval=SCAN_INTERVAL,
        )
        _LOGGER.debug(
            "Device %s polling coordinator started, interval: %ss",
            device_ip,
            SCAN_INTERVAL.total_seconds(),
        )

    async def _async_update_data(self) -> dict[str, Any]:
        """Fetch device data from the Marstek client library."""
        _LOGGER.debug("Start polling device: %s", self.device_ip)
        current_data = self.data or {}

        if self.udp_client.is_polling_paused(self.device_ip):
            _LOGGER.debug(
                "Polling paused for device: %s, skipping update", self.device_ip
            )
            return current_data

        result_data = await self.udp_client.get_device_status(
            self.device_ip,
            previous_data=current_data,
        )

        defaults = _default_status_data(self.device_ip, current_data)
        defaults.update(result_data)
        defaults["device_ip"] = self.device_ip

        return defaults


class MarstekSensor(CoordinatorEntity, SensorEntity):
    """Representation of a Marstek sensor."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: DataUpdateCoordinator,
        device_info: dict[str, Any],
        sensor_type: str,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        self._device_info = device_info
        self._sensor_type = sensor_type
        self._device_id = device_info.get("mac") or device_info.get("ip", "Unknown")
        self._attr_translation_key = sensor_type
        self._attr_device_info = {
            "identifiers": {(DOMAIN, self._device_id)},
            "name": f"Marstek {device_info['device_type']} v{device_info['version']}",
            "manufacturer": "Marstek",
            "model": device_info["device_type"],
            "sw_version": str(device_info["version"]),
            "hw_version": device_info.get("wifi_mac", ""),
        }

    @property
    def unique_id(self) -> str:
        """Return a unique ID."""
        device_id = self._device_info.get("mac") or self._device_info.get(
            "ip", "unknown"
        )
        unique_id = f"{device_id}_{self._sensor_type}"
        _LOGGER.debug(
            "Generate sensor unique_id: %s (ip=%s, mac=%s, type=%s)",
            unique_id,
            self._device_info.get("ip"),
            self._device_info.get("mac"),
            self._sensor_type,
        )
        return unique_id

    @property
    def native_value(self) -> Any:
        """Return the state of the sensor."""
        if not self.coordinator.data:
            return None
        return self.coordinator.data.get(self._sensor_type)


class MarstekBatterySensor(MarstekSensor):
    """Representation of a Marstek battery sensor."""

    def __init__(
        self,
        coordinator: DataUpdateCoordinator,
        device_info: dict[str, Any],
    ) -> None:
        """Initialize the battery sensor."""
        super().__init__(coordinator, device_info, "battery_soc")
        self._attr_native_unit_of_measurement = PERCENTAGE
        self._attr_state_class = SensorStateClass.MEASUREMENT
        self._attr_icon = "mdi:battery"

    @property
    def native_value(self) -> int | None:
        """Return the battery level."""
        if not self.coordinator.data:
            return None
        return int(self.coordinator.data.get("battery_soc", 0))


class MarstekPowerSensor(MarstekSensor):
    """Representation of a Marstek power sensor."""

    def __init__(
        self,
        coordinator: DataUpdateCoordinator,
        device_info: dict[str, Any],
    ) -> None:
        """Initialize the power sensor."""
        super().__init__(coordinator, device_info, "battery_power")
        self._attr_native_unit_of_measurement = UnitOfPower.WATT
        self._attr_state_class = SensorStateClass.MEASUREMENT
        self._attr_icon = "mdi:flash"

    @property
    def native_value(self) -> int | None:
        """Return the battery power."""
        if not self.coordinator.data:
            return None
        return int(self.coordinator.data.get("battery_power", 0))


class MarstekDeviceInfoSensor(MarstekSensor):
    """Representation of a Marstek device info sensor."""

    def __init__(
        self,
        coordinator: DataUpdateCoordinator,
        device_info: dict[str, Any],
        info_type: str,
    ) -> None:
        """Initialize the device info sensor."""
        super().__init__(coordinator, device_info, info_type)
        self._info_type = info_type
        self._attr_icon = "mdi:information"
        # Force as text sensor to avoid graph cards
        self._attr_device_class = None
        self._attr_state_class = None

    @property
    def native_value(self) -> str | None:
        """Return the device info."""
        if self._info_type == "device_ip":
            return self._device_info.get("ip", "")
        if self._info_type == "device_version":
            return str(self._device_info.get("version", ""))
        if self._info_type == "wifi_name":
            return self._device_info.get("wifi_name", "")
        return None


class MarstekDeviceModeSensor(MarstekSensor):
    """Representation of a Marstek device mode sensor."""

    def __init__(
        self,
        coordinator: DataUpdateCoordinator,
        device_info: dict[str, Any],
    ) -> None:
        """Initialize the device mode sensor."""
        super().__init__(coordinator, device_info, "device_mode")
        self._attr_icon = "mdi:cog"
        # Force as text sensor to avoid graph cards
        self._attr_device_class = None
        self._attr_state_class = None

    @property
    def native_value(self) -> str | None:
        """Return the device mode."""
        if not self.coordinator.data:
            return None
        return self.coordinator.data.get("device_mode", "Unknown")


class MarstekBatteryStatusSensor(MarstekSensor):
    """Representation of a Marstek battery status sensor."""

    def __init__(
        self,
        coordinator: DataUpdateCoordinator,
        device_info: dict[str, Any],
    ) -> None:
        """Initialize the battery status sensor."""
        super().__init__(coordinator, device_info, "battery_status")
        self._attr_icon = "mdi:battery"
        # Force as text sensor to avoid graph cards
        self._attr_device_class = None
        self._attr_state_class = None

    @property
    def native_value(self) -> str | None:
        """Return the battery status."""
        if not self.coordinator.data:
            return None
        return self.coordinator.data.get("battery_status", "Unknown")


class MarstekPVSensor(MarstekSensor):
    """Representation of a Marstek PV sensor."""

    def __init__(
        self,
        coordinator: DataUpdateCoordinator,
        device_info: dict[str, Any],
        pv_channel: int,
        metric_type: str,
    ) -> None:
        """Initialize the PV sensor."""
        sensor_key = f"pv{pv_channel}_{metric_type}"
        super().__init__(coordinator, device_info, sensor_key)
        self._pv_channel = pv_channel
        self._metric_type = metric_type

        # Set unit based on metric type
        if metric_type == "power":
            self._attr_native_unit_of_measurement = UnitOfPower.WATT
            self._attr_icon = "mdi:solar-power"
        elif metric_type == "voltage":
            self._attr_native_unit_of_measurement = UnitOfElectricPotential.VOLT
            self._attr_icon = "mdi:flash"
        elif metric_type == "current":
            self._attr_native_unit_of_measurement = UnitOfElectricCurrent.AMPERE
            self._attr_icon = "mdi:current-ac"
        elif metric_type == "state":
            self._attr_icon = "mdi:state-machine"
            self._attr_device_class = None
            self._attr_state_class = None
        else:
            self._attr_icon = "mdi:solar-panel"

        if metric_type != "state":
            self._attr_state_class = SensorStateClass.MEASUREMENT

    @property
    def native_value(self) -> int | float | None:
        """Return the PV metric value."""
        if not self.coordinator.data:
            return None
        return self.coordinator.data.get(self._sensor_type, 0)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Marstek sensors based on a config entry."""
    device_ip = config_entry.data["host"]
    _LOGGER.info("Setting up Marstek sensors: %s", device_ip)

    udp_client: MarstekUDPClient = config_entry.runtime_data

    # Build device info from config entry
    device_info = {
        "ip": config_entry.data["host"],
        "mac": config_entry.data["mac"],
        "device_type": config_entry.data.get("device_type", "Unknown"),
        "version": config_entry.data.get("version", 0),
        "wifi_name": config_entry.data.get("wifi_name", ""),
        "wifi_mac": config_entry.data.get("wifi_mac", ""),
        "ble_mac": config_entry.data.get("ble_mac", ""),
    }

    # Create coordinator for this device
    coordinator = MarstekDataUpdateCoordinator(hass, udp_client, device_info["ip"])

    # Create sensor entities - battery SoC, grid power, device mode, battery status, device IP, version
    sensors = [
        MarstekBatterySensor(coordinator, device_info),  # Battery SoC
        MarstekPowerSensor(coordinator, device_info),  # Grid power
        MarstekDeviceModeSensor(coordinator, device_info),  # Device operating mode
        MarstekBatteryStatusSensor(
            coordinator, device_info
        ),  # Battery charge/discharge status
        MarstekDeviceInfoSensor(coordinator, device_info, "device_ip"),  # Device IP
        MarstekDeviceInfoSensor(
            coordinator, device_info, "device_version"
        ),  # Version number
    ]

    # Add PV sensors for all 4 PV channels
    pv_sensors = [
        MarstekPVSensor(coordinator, device_info, pv_channel, metric_type)
        for pv_channel in range(1, 5)
        for metric_type in ["power", "voltage", "current", "state"]
    ]
    sensors.extend(pv_sensors)

    _LOGGER.info("Device %s sensors set up, total %d", device_ip, len(sensors))
    async_add_entities(sensors)
