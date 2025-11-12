"""Data update coordinator for Marstek devices."""

from __future__ import annotations

import asyncio
from datetime import timedelta
import logging
from typing import Any

from pymarstek import MarstekUDPClient, get_es_mode, get_pv_status

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from .const import DEFAULT_UDP_PORT

_LOGGER = logging.getLogger(__name__)

SCAN_INTERVAL = timedelta(seconds=10)


class MarstekDataUpdateCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    """Per-device data update coordinator."""

    def __init__(
        self,
        hass: HomeAssistant,
        config_entry: ConfigEntry,
        udp_client: MarstekUDPClient,
        device_ip: str,
    ) -> None:
        """Initialize the coordinator."""
        self.udp_client = udp_client
        self.device_ip = device_ip
        super().__init__(
            hass,
            _LOGGER,
            name=f"Marstek {device_ip}",
            update_interval=SCAN_INTERVAL,
            config_entry=config_entry,
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

        if self.udp_client.is_polling_paused(self.device_ip):
            _LOGGER.debug(
                "Polling paused for device: %s, skipping update", self.device_ip
            )
            return self.data or {}

        current_data = self.data or {}
        result_data: dict[str, Any] = {
            "battery_soc": current_data.get("battery_soc", 0),
            "battery_power": current_data.get("battery_power", 0),
            "device_mode": current_data.get("device_mode", "Unknown"),
            "battery_status": current_data.get("battery_status", "Unknown"),
            "device_ip": self.device_ip,
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

        async def es_status_request() -> bool:
            try:
                _LOGGER.debug("Begin ES.GetMode query to device: %s", self.device_ip)
                mode_as_status_command = get_es_mode(0)
                _LOGGER.debug(
                    "Sensor send -> %s | %s", self.device_ip, mode_as_status_command
                )
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

                battery_soc = status_data.get(
                    "bat_soc", result_data.get("battery_soc", 0)
                )
                result_data["battery_soc"] = battery_soc
                ongrid_power = status_data.get(
                    "ongrid_power", result_data.get("battery_power", 0)
                )
                result_data["battery_power"] = abs(ongrid_power)

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
            return True

        async def pv_status_request() -> bool:
            try:
                _LOGGER.debug("Begin PV.GetStatus query to device: %s", self.device_ip)
                pv_status_command = get_pv_status(0)
                _LOGGER.debug(
                    "Sensor send -> %s | %s", self.device_ip, pv_status_command
                )
                pv_status_result = await self.udp_client.send_request(
                    pv_status_command, self.device_ip, DEFAULT_UDP_PORT, timeout=2.5
                )
                _LOGGER.debug(
                    "Sensor recv <- %s | %s", self.device_ip, pv_status_result
                )

                pv_data = pv_status_result.get("result", {})
                _LOGGER.debug("PV.GetStatus raw: %s", pv_status_result)
                _LOGGER.debug("PV.GetStatus data: %s", pv_data)

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
            return True

        try:
            await es_status_request()
        except (TimeoutError, OSError, ValueError) as err:
            _LOGGER.error(
                "Device %s ES.GetMode request failed: %s", self.device_ip, err
            )

        await asyncio.sleep(2)

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
