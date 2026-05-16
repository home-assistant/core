"""Sensor platform for Marstek devices."""

from __future__ import annotations

import logging
from typing import Any, cast

from homeassistant.components.sensor import SensorEntity, SensorStateClass
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    CONF_HOST,
    PERCENTAGE,
    EntityCategory,
    UnitOfElectricCurrent,
    UnitOfElectricPotential,
    UnitOfPower,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.typing import StateType
from homeassistant.helpers.update_coordinator import CoordinatorEntity

try:
    from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
except ImportError:
    # Fallback for older Home Assistant versions
    from collections.abc import Iterable
    from typing import TYPE_CHECKING, Protocol

    if TYPE_CHECKING:
        from homeassistant.helpers.entity import Entity
    else:
        Entity = object  # type: ignore[assignment, misc]

    class AddConfigEntryEntitiesCallback(Protocol):  # type: ignore[no-redef]
        """Protocol type for EntityPlatform.add_entities callback (fallback)."""

        def __call__(
            self,
            new_entities: Iterable[Entity],
            update_before_add: bool = False,
        ) -> None:
            """Define add_entities type."""


from . import MarstekConfigEntry
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
        config_entry: ConfigEntry | None = None,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        self._device_info = device_info
        self._sensor_type = sensor_type
        self._config_entry = config_entry
        # Use BLE-MAC as device identifier for stability (beardhatcode & mik-laj feedback)
        # BLE-MAC is more stable than IP and ensures device history continuity
        device_identifier = (
            device_info.get("ble_mac")
            or device_info.get("mac")
            or device_info.get("wifi_mac")
            or device_info["ip"]
        )
        # Get current IP for device name (supports dynamic IP updates)
        device_ip = (
            config_entry.data.get(CONF_HOST)
            if config_entry
            else device_info.get("ip", "Unknown")
        )
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, device_identifier)},
            name=f"Marstek {device_info['device_type']} v{device_info['version']} ({device_ip})",
            manufacturer="Marstek",
            model=device_info["device_type"],
            sw_version=str(device_info["version"]),
            hw_version=device_info.get("wifi_mac", ""),
        )

    @property
    def unique_id(self) -> str:
        """Return a unique ID."""
        # Use BLE-MAC as device identifier for stability (beardhatcode & mik-laj feedback)
        device_id = (
            self._device_info.get("ble_mac")
            or self._device_info.get("mac")
            or self._device_info.get("wifi_mac")
            or self._device_info.get("ip", "unknown")
        )
        return f"{device_id}_{self._sensor_type}"

    def _get_current_ip(self) -> str:
        """Get current device IP from config_entry (supports dynamic IP updates)."""
        if self._config_entry:
            return self._config_entry.data.get(
                CONF_HOST, self._device_info.get("ip", "Unknown")
            )
        return self._device_info.get("ip", "Unknown")

    @property
    def name(self) -> str:
        """Return the name of the sensor."""
        return self._sensor_type.replace("_", " ").title()

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

    _attr_translation_key = "battery_level"
    _attr_native_unit_of_measurement = PERCENTAGE
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_icon = "mdi:battery"

    def __init__(
        self,
        coordinator: MarstekDataUpdateCoordinator,
        device_info: dict[str, Any],
        config_entry: ConfigEntry | None = None,
    ) -> None:
        """Initialize the battery sensor."""
        super().__init__(coordinator, device_info, "battery_soc", config_entry)

    @property
    def native_value(self) -> StateType:
        """Return the battery level."""
        if not self.coordinator.data:
            return None
        return int(self.coordinator.data.get("battery_soc", 0))


class MarstekPowerSensor(MarstekSensor):
    """Representation of a Marstek power sensor."""

    _attr_native_unit_of_measurement = UnitOfPower.WATT
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_icon = "mdi:flash"

    def __init__(
        self,
        coordinator: MarstekDataUpdateCoordinator,
        device_info: dict[str, Any],
        config_entry: ConfigEntry | None = None,
    ) -> None:
        """Initialize the power sensor."""
        super().__init__(coordinator, device_info, "battery_power", config_entry)

    @property
    def name(self) -> str:
        """Return the name of the sensor."""
        return "Grid Power"

    @property
    def native_value(self) -> StateType:
        """Return the battery power."""
        if not self.coordinator.data:
            return None
        return int(self.coordinator.data.get("battery_power", 0))


class MarstekDeviceInfoSensor(MarstekSensor):
    """Representation of a Marstek device info sensor."""

    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(
        self,
        coordinator: MarstekDataUpdateCoordinator,
        device_info: dict[str, Any],
        info_type: str,
        config_entry: ConfigEntry | None = None,
    ) -> None:
        """Initialize the device info sensor."""
        super().__init__(coordinator, device_info, info_type, config_entry)
        self._info_type = info_type
        self._attr_icon = "mdi:information"
        self._attr_device_class = None
        self._attr_state_class = None

    @property
    def name(self) -> str:
        """Return the name of the sensor."""
        info_type_names = {
            "device_ip": "Device IP",
            "device_version": "Device version",
            "wifi_name": "Wi-Fi name",
            "ble_mac": "BLE MAC",
            "wifi_mac": "Wi-Fi MAC",
            "mac": "MAC address",
        }
        return info_type_names.get(self._info_type, self._info_type.replace("_", " "))

    @property
    def native_value(self) -> StateType:
        """Return the device info."""
        if self._info_type == "device_ip":
            # Get current IP from config_entry if available (supports dynamic IP updates)
            if self._config_entry:
                return self._config_entry.data.get(CONF_HOST, "")
            return self._device_info.get("ip", "")
        if self._info_type == "device_version":
            return str(self._device_info.get("version", ""))
        if self._info_type == "wifi_name":
            return self._device_info.get("wifi_name", "")
        if self._info_type == "ble_mac":
            return self._device_info.get("ble_mac", "")
        if self._info_type == "wifi_mac":
            return self._device_info.get("wifi_mac", "")
        if self._info_type == "mac":
            return self._device_info.get("mac", "")
        return None


class MarstekDeviceModeSensor(MarstekSensor):
    """Representation of a Marstek device mode sensor."""

    _attr_icon = "mdi:cog"
    _attr_device_class = None
    _attr_state_class = None

    def __init__(
        self,
        coordinator: MarstekDataUpdateCoordinator,
        device_info: dict[str, Any],
        config_entry: ConfigEntry | None = None,
    ) -> None:
        """Initialize the device mode sensor."""
        super().__init__(coordinator, device_info, "device_mode", config_entry)

    @property
    def name(self) -> str:
        """Return the name of the sensor."""
        return "Device Mode"


class MarstekBatteryStatusSensor(MarstekSensor):
    """Representation of a Marstek battery status sensor."""

    _attr_icon = "mdi:battery"
    _attr_device_class = None
    _attr_state_class = None

    def __init__(
        self,
        coordinator: MarstekDataUpdateCoordinator,
        device_info: dict[str, Any],
        config_entry: ConfigEntry | None = None,
    ) -> None:
        """Initialize the battery status sensor."""
        super().__init__(coordinator, device_info, "battery_status", config_entry)

    @property
    def name(self) -> str:
        """Return the name of the sensor."""
        return "Battery Status"


class MarstekPVSensor(MarstekSensor):
    """Representation of a Marstek PV sensor."""

    def __init__(
        self,
        coordinator: MarstekDataUpdateCoordinator,
        device_info: dict[str, Any],
        pv_channel: int,
        metric_type: str,
        config_entry: ConfigEntry | None = None,
    ) -> None:
        """Initialize the PV sensor."""
        sensor_key = f"pv{pv_channel}_{metric_type}"
        super().__init__(coordinator, device_info, sensor_key, config_entry)
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
        metric_name = self._metric_type.replace("_", " ").title()
        return f"PV{self._pv_channel} {metric_name}"

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
    # Use shared coordinator and device_info from __init__.py (mik-laj feedback)
    coordinator = config_entry.runtime_data.coordinator
    device_info = config_entry.runtime_data.device_info
    device_ip = device_info["ip"]
    _LOGGER.info("Setting up Marstek sensors: %s", device_ip)

    sensors: list[MarstekSensor] = [
        MarstekBatterySensor(coordinator, device_info, config_entry),
        MarstekPowerSensor(coordinator, device_info, config_entry),
        MarstekDeviceModeSensor(coordinator, device_info, config_entry),
        MarstekBatteryStatusSensor(coordinator, device_info, config_entry),
        MarstekDeviceInfoSensor(coordinator, device_info, "device_ip", config_entry),
        MarstekDeviceInfoSensor(
            coordinator, device_info, "device_version", config_entry
        ),
        MarstekDeviceInfoSensor(coordinator, device_info, "ble_mac", config_entry),
        MarstekDeviceInfoSensor(coordinator, device_info, "wifi_mac", config_entry),
        MarstekDeviceInfoSensor(coordinator, device_info, "mac", config_entry),
    ]

    sensors.extend(
        MarstekPVSensor(coordinator, device_info, pv_channel, metric_type, config_entry)
        for pv_channel in range(1, 5)
        for metric_type in ("power", "voltage", "current", "state")
    )

    _LOGGER.info("Device %s sensors set up, total %d", device_ip, len(sensors))
    async_add_entities(sensors)
