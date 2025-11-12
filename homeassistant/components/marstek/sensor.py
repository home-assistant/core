"""Sensor platform for Marstek devices."""

from __future__ import annotations

import logging
from typing import Any, cast

from homeassistant.components.sensor import SensorEntity, SensorStateClass
from homeassistant.const import (
    PERCENTAGE,
    UnitOfElectricCurrent,
    UnitOfElectricPotential,
    UnitOfPower,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.typing import StateType
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import MarstekConfigEntry, MarstekRuntimeData
from .const import DOMAIN
from .coordinator import MarstekDataUpdateCoordinator

_LOGGER = logging.getLogger(__name__)


class MarstekSensor(CoordinatorEntity[MarstekDataUpdateCoordinator], SensorEntity):
    """Representation of a Marstek sensor."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: MarstekDataUpdateCoordinator,
        device_info: dict[str, Any],
        sensor_type: str,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        self._device_info = device_info
        self._sensor_type = sensor_type
        self._attr_device_info = {
            "identifiers": {(DOMAIN, device_info["ip"])},
            "name": f"Marstek {device_info['device_type']} v{device_info['version']}",
            "manufacturer": "Marstek",
            "model": device_info["device_type"],
            "sw_version": str(device_info["version"]),
            "hw_version": device_info.get("wifi_mac", ""),
        }

    @property
    def unique_id(self) -> str:
        """Return a unique ID."""
        device_id = self._device_info.get("ip") or self._device_info.get(
            "mac", "unknown"
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
    def name(self) -> str:
        """Return the name of the sensor."""
        device_ip = self._device_info.get("ip", "Unknown")
        sensor_name = self._sensor_type.replace("_", " ").title()
        return f"{sensor_name} ({device_ip})"

    @property
    def native_value(self) -> StateType:
        """Return the state of the sensor."""
        if not self.coordinator.data:
            return None
        value = self.coordinator.data.get(self._sensor_type)
        if isinstance(value, (int, float, str)):
            return cast(StateType, value)
        return None


class MarstekBatterySensor(MarstekSensor):
    """Representation of a Marstek battery sensor."""

    def __init__(
        self,
        coordinator: MarstekDataUpdateCoordinator,
        device_info: dict[str, Any],
    ) -> None:
        """Initialize the battery sensor."""
        super().__init__(coordinator, device_info, "battery_soc")
        self._attr_native_unit_of_measurement = PERCENTAGE
        self._attr_state_class = SensorStateClass.MEASUREMENT
        self._attr_icon = "mdi:battery"

    @property
    def name(self) -> str:
        """Return the name of the sensor."""
        device_ip = self._device_info.get("ip", "Unknown")
        return f"Battery Level ({device_ip})"

    @property
    def native_value(self) -> StateType:
        """Return the battery level."""
        if not self.coordinator.data:
            return None
        return int(self.coordinator.data.get("battery_soc", 0))


class MarstekPowerSensor(MarstekSensor):
    """Representation of a Marstek power sensor."""

    def __init__(
        self,
        coordinator: MarstekDataUpdateCoordinator,
        device_info: dict[str, Any],
    ) -> None:
        """Initialize the power sensor."""
        super().__init__(coordinator, device_info, "battery_power")
        self._attr_native_unit_of_measurement = UnitOfPower.WATT
        self._attr_state_class = SensorStateClass.MEASUREMENT
        self._attr_icon = "mdi:flash"

    @property
    def name(self) -> str:
        """Return the name of the sensor."""
        device_ip = self._device_info.get("ip", "Unknown")
        return f"Grid Power ({device_ip})"

    @property
    def native_value(self) -> StateType:
        """Return the battery power."""
        if not self.coordinator.data:
            return None
        return int(self.coordinator.data.get("battery_power", 0))


class MarstekDeviceInfoSensor(MarstekSensor):
    """Representation of a Marstek device info sensor."""

    def __init__(
        self,
        coordinator: MarstekDataUpdateCoordinator,
        device_info: dict[str, Any],
        info_type: str,
    ) -> None:
        """Initialize the device info sensor."""
        super().__init__(coordinator, device_info, info_type)
        self._info_type = info_type
        self._attr_icon = "mdi:information"
        self._attr_device_class = None
        self._attr_state_class = None

    @property
    def name(self) -> str:
        """Return the name of the sensor."""
        return self._info_type.replace("_", " ").title()

    @property
    def native_value(self) -> StateType:
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
        coordinator: MarstekDataUpdateCoordinator,
        device_info: dict[str, Any],
    ) -> None:
        """Initialize the device mode sensor."""
        super().__init__(coordinator, device_info, "device_mode")
        self._attr_icon = "mdi:cog"
        self._attr_device_class = None
        self._attr_state_class = None

    @property
    def name(self) -> str:
        """Return the name of the sensor."""
        device_ip = self._device_info.get("ip", "Unknown")
        return f"Device Mode ({device_ip})"


class MarstekBatteryStatusSensor(MarstekSensor):
    """Representation of a Marstek battery status sensor."""

    def __init__(
        self,
        coordinator: MarstekDataUpdateCoordinator,
        device_info: dict[str, Any],
    ) -> None:
        """Initialize the battery status sensor."""
        super().__init__(coordinator, device_info, "battery_status")
        self._attr_icon = "mdi:battery"
        self._attr_device_class = None
        self._attr_state_class = None

    @property
    def name(self) -> str:
        """Return the name of the sensor."""
        device_ip = self._device_info.get("ip", "Unknown")
        return f"Battery Status ({device_ip})"


class MarstekPVSensor(MarstekSensor):
    """Representation of a Marstek PV sensor."""

    def __init__(
        self,
        coordinator: MarstekDataUpdateCoordinator,
        device_info: dict[str, Any],
        pv_channel: int,
        metric_type: str,
    ) -> None:
        """Initialize the PV sensor."""
        sensor_key = f"pv{pv_channel}_{metric_type}"
        super().__init__(coordinator, device_info, sensor_key)
        self._pv_channel = pv_channel
        self._metric_type = metric_type

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
    def name(self) -> str:
        """Return the name of the sensor."""
        device_ip = self._device_info.get("ip", "Unknown")
        metric_name = self._metric_type.replace("_", " ").title()
        return f"PV{self._pv_channel} {metric_name} ({device_ip})"

    @property
    def native_value(self) -> StateType:
        """Return the PV metric value."""
        if not self.coordinator.data:
            return None
        value = self.coordinator.data.get(self._sensor_type)
        if isinstance(value, (int, float)):
            return cast(StateType, value)
        return None


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: MarstekConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Marstek sensors based on a config entry."""
    device_ip = config_entry.data["host"]
    _LOGGER.info("Setting up Marstek sensors: %s", device_ip)

    runtime_data = config_entry.runtime_data
    if runtime_data is None:
        runtime_data = MarstekRuntimeData(hass.data[DOMAIN]["udp_client"])
        config_entry.runtime_data = runtime_data
    udp_client = runtime_data.udp_client

    device_info = {
        "ip": config_entry.data["host"],
        "mac": config_entry.data.get("mac", ""),
        "device_type": config_entry.data.get("device_type", "Unknown"),
        "version": config_entry.data.get("version", 0),
        "wifi_name": config_entry.data.get("wifi_name", ""),
        "wifi_mac": config_entry.data.get("wifi_mac", ""),
        "ble_mac": config_entry.data.get("ble_mac", ""),
    }

    coordinator = MarstekDataUpdateCoordinator(
        hass, config_entry, udp_client, device_info["ip"]
    )
    await coordinator.async_config_entry_first_refresh()

    sensors: list[MarstekSensor] = [
        MarstekBatterySensor(coordinator, device_info),
        MarstekPowerSensor(coordinator, device_info),
        MarstekDeviceModeSensor(coordinator, device_info),
        MarstekBatteryStatusSensor(coordinator, device_info),
        MarstekDeviceInfoSensor(coordinator, device_info, "device_ip"),
        MarstekDeviceInfoSensor(coordinator, device_info, "device_version"),
    ]

    sensors.extend(
        MarstekPVSensor(coordinator, device_info, pv_channel, metric_type)
        for pv_channel in range(1, 5)
        for metric_type in ("power", "voltage", "current", "state")
    )

    _LOGGER.info("Device %s sensors set up, total %d", device_ip, len(sensors))
    async_add_entities(sensors)
