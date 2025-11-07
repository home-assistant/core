"""Sensor platform for Marstek devices."""

from __future__ import annotations

import asyncio
from datetime import timedelta
import logging
from typing import Any

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

from .command_builder import get_es_mode, get_pv_status
from .const import DEFAULT_UDP_PORT, DOMAIN
from .udp_client import MarstekUDPClient

_LOGGER = logging.getLogger(__name__)

# Update interval for polling device data
SCAN_INTERVAL = timedelta(seconds=10)


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
        """Fetch all data using a single ES.GetMode request."""
        _LOGGER.debug("Start polling device: %s", self.device_ip)
        _LOGGER.debug("UDP client: %s", self.udp_client)

        # Check if polling is paused for this device
        if self.udp_client.is_polling_paused(self.device_ip):
            _LOGGER.debug(
                "Polling paused for device: %s, skipping update", self.device_ip
            )
            # Return existing data to avoid clearing the state
            return self.data or {}

        # Use existing data as defaults (preserve previous values)
        current_data = self.data or {}
        result_data = {
            "battery_soc": current_data.get("battery_soc", 0),
            "battery_power": current_data.get("battery_power", 0),
            "device_mode": current_data.get("device_mode", "Unknown"),
            "battery_status": current_data.get("battery_status", "Unknown"),
            "device_ip": self.device_ip,
            "last_update": asyncio.get_event_loop().time(),
            # PV data - with defaults
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

        # Delay helper
        def delay(ms):
            return asyncio.sleep(ms / 1000.0)

        # Single ES.GetMode request (includes bat_soc and ongrid_power)
        async def es_status_request():
            try:
                _LOGGER.debug("Begin ES.GetMode query to device: %s", self.device_ip)
                mode_as_status_command = get_es_mode(0)
                _LOGGER.debug(
                    "Sensor send -> %s | %s", self.device_ip, mode_as_status_command
                )
                # Wait up to 2.5s
                mode_as_status_result = await self.udp_client.send_request(
                    mode_as_status_command,
                    self.device_ip,
                    DEFAULT_UDP_PORT,
                    timeout=2.5,
                )
                _LOGGER.debug(
                    "Sensor recv <- %s | %s", self.device_ip, mode_as_status_result
                )

                status_data = mode_as_status_result.get("result", {})
                _LOGGER.debug("ES.GetMode raw: %s", mode_as_status_result)
                _LOGGER.debug("ES.GetMode data: %s", status_data)

                # SOC and power
                battery_soc = status_data.get(
                    "bat_soc", result_data.get("battery_soc", 0)
                )
                result_data["battery_soc"] = battery_soc
                ongrid_power = status_data.get(
                    "ongrid_power", result_data.get("battery_power", 0)
                )
                result_data["battery_power"] = abs(ongrid_power)

                # Operating mode and battery status
                device_mode = status_data.get("mode", "Unknown")
                result_data["device_mode"] = device_mode
                if ongrid_power > 0:
                    battery_status = "Selling"
                elif ongrid_power < 0:
                    battery_status = "Charging"
                else:
                    battery_status = "Idle"
                result_data["battery_status"] = battery_status

                _LOGGER.debug(
                    "Device %s OK: SOC=%s%%, ongrid_power=%sW(abs=%sW), mode=%s, status=%s",
                    self.device_ip,
                    battery_soc,
                    ongrid_power,
                    result_data["battery_power"],
                    device_mode,
                    battery_status,
                )
            except (TimeoutError, OSError, ValueError) as err:
                _LOGGER.debug(
                    "ES.GetMode failed (timeout/exception): %s %s",
                    self.device_ip,
                    str(err),
                )
                return False
            else:
                return True

        # Already covered by es_status_request, keep for structure compatibility
        async def es_mode_request():
            return True

        # PV.GetStatus request
        async def pv_status_request():
            try:
                _LOGGER.debug("Begin PV.GetStatus query to device: %s", self.device_ip)
                pv_status_command = get_pv_status(0)
                _LOGGER.debug(
                    "Sensor send -> %s | %s", self.device_ip, pv_status_command
                )
                # Wait up to 2.5s
                pv_status_result = await self.udp_client.send_request(
                    pv_status_command, self.device_ip, DEFAULT_UDP_PORT, timeout=2.5
                )
                _LOGGER.debug(
                    "Sensor recv <- %s | %s", self.device_ip, pv_status_result
                )

                pv_data = pv_status_result.get("result", {})
                _LOGGER.debug("PV.GetStatus raw: %s", pv_status_result)
                _LOGGER.debug("PV.GetStatus data: %s", pv_data)

                # PV1 data
                result_data["pv1_power"] = pv_data.get(
                    "pv1_power", result_data.get("pv1_power", 0)
                )
                result_data["pv1_voltage"] = pv_data.get(
                    "pv1_voltage", result_data.get("pv1_voltage", 0)
                )
                result_data["pv1_current"] = pv_data.get(
                    "pv1_current", result_data.get("pv1_current", 0)
                )
                result_data["pv1_state"] = pv_data.get(
                    "pv1_state", result_data.get("pv1_state", 0)
                )

                # PV2 data
                result_data["pv2_power"] = pv_data.get(
                    "pv2_power", result_data.get("pv2_power", 0)
                )
                result_data["pv2_voltage"] = pv_data.get(
                    "pv2_voltage", result_data.get("pv2_voltage", 0)
                )
                result_data["pv2_current"] = pv_data.get(
                    "pv2_current", result_data.get("pv2_current", 0)
                )
                result_data["pv2_state"] = pv_data.get(
                    "pv2_state", result_data.get("pv2_state", 0)
                )

                # PV3 data
                result_data["pv3_power"] = pv_data.get(
                    "pv3_power", result_data.get("pv3_power", 0)
                )
                result_data["pv3_voltage"] = pv_data.get(
                    "pv3_voltage", result_data.get("pv3_voltage", 0)
                )
                result_data["pv3_current"] = pv_data.get(
                    "pv3_current", result_data.get("pv3_current", 0)
                )
                result_data["pv3_state"] = pv_data.get(
                    "pv3_state", result_data.get("pv3_state", 0)
                )

                # PV4 data
                result_data["pv4_power"] = pv_data.get(
                    "pv4_power", result_data.get("pv4_power", 0)
                )
                result_data["pv4_voltage"] = pv_data.get(
                    "pv4_voltage", result_data.get("pv4_voltage", 0)
                )
                result_data["pv4_current"] = pv_data.get(
                    "pv4_current", result_data.get("pv4_current", 0)
                )
                result_data["pv4_state"] = pv_data.get(
                    "pv4_state", result_data.get("pv4_state", 0)
                )

                _LOGGER.debug(
                    "Device %s PV data: PV1=%sW, PV2=%sW, PV3=%sW, PV4=%sW",
                    self.device_ip,
                    result_data["pv1_power"],
                    result_data["pv2_power"],
                    result_data["pv3_power"],
                    result_data["pv4_power"],
                )
            except (TimeoutError, OSError, ValueError) as err:
                _LOGGER.debug(
                    "PV.GetStatus failed (timeout/exception): %s %s",
                    self.device_ip,
                    str(err),
                )
                return False
            else:
                return True

        # Execute requests sequentially and independently
        # Each request runs independently and failures don't block the other request

        # Send ES.GetMode request for battery and mode data
        try:
            await es_status_request()
        except (TimeoutError, OSError, ValueError) as err:
            _LOGGER.error(
                "Device %s ES.GetMode request failed: %s", self.device_ip, err
            )

        # Wait 2 seconds before sending the next request
        await delay(2000)

        # Send PV.GetStatus request for PV data
        try:
            await pv_status_request()
        except (TimeoutError, OSError, ValueError) as err:
            _LOGGER.error(
                "Device %s PV.GetStatus request failed: %s", self.device_ip, err
            )

        _LOGGER.debug(
            "Device %s poll done: SOC %s%%, Power %sW, Mode %s, Status %s",
            self.device_ip,
            result_data["battery_soc"],
            result_data["battery_power"],
            result_data["device_mode"],
            result_data["battery_status"],
        )

        return result_data


class MarstekSensor(CoordinatorEntity, SensorEntity):
    """Representation of a Marstek sensor."""

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
        self._attr_device_info = {
            # Use IP as identifier to avoid merge on duplicate MACs
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
        # Use IP as unique identifier to avoid duplicate MAC collisions
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
    def name(self) -> str:
        """Return the name of the sensor."""
        device_ip = self._device_info.get("ip", "Unknown")
        return f"Battery Level ({device_ip})"

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
    def name(self) -> str:
        """Return the name of the sensor."""
        device_ip = self._device_info.get("ip", "Unknown")
        return f"Grid Power ({device_ip})"

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
    def name(self) -> str:
        """Return the name of the sensor."""
        return f"{self._info_type.replace('_', ' ').title()}"

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
    def name(self) -> str:
        """Return the name of the sensor."""
        device_ip = self._device_info.get("ip", "Unknown")
        return f"Device Mode ({device_ip})"

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
    def name(self) -> str:
        """Return the name of the sensor."""
        device_ip = self._device_info.get("ip", "Unknown")
        return f"Battery Status ({device_ip})"

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
    def name(self) -> str:
        """Return the name of the sensor."""
        device_ip = self._device_info.get("ip", "Unknown")
        metric_name = self._metric_type.replace("_", " ").title()
        return f"PV{self._pv_channel} {metric_name} ({device_ip})"

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

    # Use a shared global UDP client to avoid port conflicts across instances
    store = hass.data.setdefault(DOMAIN, {})
    if "udp_client" not in store:
        store["udp_client"] = MarstekUDPClient(hass)
        await store["udp_client"].async_setup()
    udp_client = store["udp_client"]

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
