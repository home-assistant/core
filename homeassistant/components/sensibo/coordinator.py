"""DataUpdateCoordinator for the Sensibo integration."""
from __future__ import annotations

from datetime import timedelta
from typing import Any

import pysensibo

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_API_KEY
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DEFAULT_SCAN_INTERVAL, DOMAIN, LOGGER, TIMEOUT


class SensiboDataUpdateCoordinator(DataUpdateCoordinator):
    """A Sensibo Data Update Coordinator."""

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        """Initialize the Sensibo coordinator."""
        self.client = pysensibo.SensiboClient(
            entry.data[CONF_API_KEY],
            session=async_get_clientsession(hass),
            timeout=TIMEOUT,
        )
        super().__init__(
            hass,
            LOGGER,
            name=DOMAIN,
            update_interval=timedelta(seconds=DEFAULT_SCAN_INTERVAL),
        )

    async def _async_update_data(self) -> dict[str, dict[str, Any]]:
        """Fetch data from Sensibo."""

        devices = []
        try:
            for dev in await self.client.async_get_devices():
                devices.append(dev)
        except (pysensibo.SensiboError) as error:
            raise UpdateFailed from error

        device_data: dict[str, dict[str, Any]] = {}
        for dev in devices:
            unique_id = dev["id"]
            name = dev["room"]["name"]
            temperature = dev["measurements"].get("temperature", 0.0)
            humidity = dev["measurements"].get("humidity", 0)
            ac_states = dev["acState"]
            target_temperature = ac_states.get("targetTemperature")
            hvac_mode = ac_states.get("mode")
            running = ac_states.get("on")
            fan_mode = ac_states.get("fanLevel")
            swing_mode = ac_states.get("swing")
            available = dev["connectionStatus"].get("isAlive", True)
            capabilities = dev["remoteCapabilities"]
            hvac_modes = list(capabilities["modes"])
            if hvac_modes:
                hvac_modes.append("off")
            current_capabilities = capabilities["modes"][ac_states.get("mode")]
            fan_modes = current_capabilities.get("fanLevels")
            swing_modes = current_capabilities.get("swing")
            temperature_unit_key = dev.get("temperatureUnit") or ac_states.get(
                "temperatureUnit"
            )
            temperatures_list = (
                current_capabilities["temperatures"]
                .get(temperature_unit_key, {})
                .get("values", [0, 1])
            )
            if temperatures_list:
                temperature_step = temperatures_list[1] - temperatures_list[0]
            features = list(ac_states)
            state = hvac_mode if hvac_mode else "off"

            fw_ver = dev["firmwareVersion"]
            fw_type = dev["firmwareType"]
            model = dev["productModel"]

            calibration_temp = dev["sensorsCalibration"].get("temperature", 0.0)
            calibration_hum = dev["sensorsCalibration"].get("humidity", 0.0)

            device_data[unique_id] = {
                "id": unique_id,
                "name": name,
                "ac_states": ac_states,
                "temp": temperature,
                "humidity": humidity,
                "target_temp": target_temperature,
                "hvac_mode": hvac_mode,
                "on": running,
                "fan_mode": fan_mode,
                "swing_mode": swing_mode,
                "available": available,
                "hvac_modes": hvac_modes,
                "fan_modes": fan_modes,
                "swing_modes": swing_modes,
                "temp_unit": temperature_unit_key,
                "temp_list": temperatures_list,
                "temp_step": temperature_step,
                "features": features,
                "state": state,
                "fw_ver": fw_ver,
                "fw_type": fw_type,
                "model": model,
                "calibration_temp": calibration_temp,
                "calibration_hum": calibration_hum,
                "full_capabilities": capabilities,
            }
        return device_data
