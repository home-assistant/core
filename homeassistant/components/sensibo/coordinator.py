"""DataUpdateCoordinator for the Sensibo integration."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta
from typing import Any

from pysensibo import SensiboClient
from pysensibo.exceptions import AuthenticationError, SensiboError

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_API_KEY
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DEFAULT_SCAN_INTERVAL, DOMAIN, LOGGER, TIMEOUT

MAX_POSSIBLE_STEP = 1000


@dataclass
class MotionSensor:
    """Dataclass for motionsensors."""

    id: str
    alive: bool | None = None
    motion: bool | None = None
    fw_ver: str | None = None
    fw_type: str | None = None
    is_main_sensor: bool | None = None
    battery_voltage: int | None = None
    humidity: int | None = None
    temperature: float | None = None
    model: str | None = None
    rssi: int | None = None


@dataclass
class SensiboData:
    """Dataclass for Sensibo data."""

    raw: dict
    parsed: dict


class SensiboDataUpdateCoordinator(DataUpdateCoordinator):
    """A Sensibo Data Update Coordinator."""

    data: SensiboData

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        """Initialize the Sensibo coordinator."""
        self.client = SensiboClient(
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

    async def _async_update_data(self) -> SensiboData:
        """Fetch data from Sensibo."""

        devices = []
        try:
            data = await self.client.async_get_devices()
            for dev in data["result"]:
                devices.append(dev)
        except AuthenticationError as error:
            raise ConfigEntryAuthFailed from error
        except SensiboError as error:
            raise UpdateFailed from error

        if not devices:
            raise UpdateFailed("No devices found")

        device_data: dict[str, Any] = {}
        for dev in devices:
            unique_id = dev["id"]
            mac = dev["macAddress"]
            name = dev["room"]["name"]
            temperature = dev["measurements"].get("temperature")
            humidity = dev["measurements"].get("humidity")
            ac_states = dev["acState"]
            target_temperature = ac_states.get("targetTemperature")
            hvac_mode = ac_states.get("mode")
            running = ac_states.get("on")
            fan_mode = ac_states.get("fanLevel")
            swing_mode = ac_states.get("swing")
            horizontal_swing_mode = ac_states.get("horizontalSwing")
            light_mode = ac_states.get("light")
            available = dev["connectionStatus"].get("isAlive", True)
            capabilities = dev["remoteCapabilities"]
            hvac_modes = list(capabilities["modes"])
            if hvac_modes:
                hvac_modes.append("off")
            current_capabilities = capabilities["modes"][ac_states.get("mode")]
            fan_modes = current_capabilities.get("fanLevels")
            swing_modes = current_capabilities.get("swing")
            horizontal_swing_modes = current_capabilities.get("horizontalSwing")
            light_modes = current_capabilities.get("light")
            temperature_unit_key = dev.get("temperatureUnit") or ac_states.get(
                "temperatureUnit"
            )
            temperatures_list = (
                current_capabilities["temperatures"]
                .get(temperature_unit_key, {})
                .get("values", [0, 1])
            )
            if temperatures_list:
                diff = MAX_POSSIBLE_STEP
                for i in range(len(temperatures_list) - 1):
                    if temperatures_list[i + 1] - temperatures_list[i] < diff:
                        diff = temperatures_list[i + 1] - temperatures_list[i]
                temperature_step = diff

            active_features = list(ac_states)
            full_features = set()
            for mode in capabilities["modes"]:
                if "temperatures" in capabilities["modes"][mode]:
                    full_features.add("targetTemperature")
                if "swing" in capabilities["modes"][mode]:
                    full_features.add("swing")
                if "fanLevels" in capabilities["modes"][mode]:
                    full_features.add("fanLevel")
                if "horizontalSwing" in capabilities["modes"][mode]:
                    full_features.add("horizontalSwing")
                if "light" in capabilities["modes"][mode]:
                    full_features.add("light")

            state = hvac_mode if hvac_mode else "off"

            fw_ver = dev["firmwareVersion"]
            fw_type = dev["firmwareType"]
            model = dev["productModel"]

            calibration_temp = dev["sensorsCalibration"].get("temperature")
            calibration_hum = dev["sensorsCalibration"].get("humidity")

            # Sky plus supports functionality to use motion sensor as sensor for temp and humidity
            if main_sensor := dev["mainMeasurementsSensor"]:
                measurements = main_sensor["measurements"]
                temperature = measurements.get("temperature")
                humidity = measurements.get("humidity")

            motion_sensors: dict[str, Any] = {}
            if dev["motionSensors"]:
                for sensor in dev["motionSensors"]:
                    measurement = sensor["measurements"]
                    motion_sensors[sensor["id"]] = MotionSensor(
                        id=sensor["id"],
                        alive=sensor["connectionStatus"].get("isAlive"),
                        motion=measurement.get("motion"),
                        fw_ver=sensor.get("firmwareVersion"),
                        fw_type=sensor.get("firmwareType"),
                        is_main_sensor=sensor.get("isMainSensor"),
                        battery_voltage=measurement.get("batteryVoltage"),
                        humidity=measurement.get("humidity"),
                        temperature=measurement.get("temperature"),
                        model=sensor.get("productModel"),
                        rssi=measurement.get("rssi"),
                    )

            # Add information for pure devices
            pure_conf = dev["pureBoostConfig"]
            pure_sensitivity = pure_conf.get("sensitivity") if pure_conf else None
            pure_boost_enabled = pure_conf.get("enabled") if pure_conf else None
            pm25 = dev["measurements"].get("pm25")

            device_data[unique_id] = {
                "id": unique_id,
                "mac": mac,
                "name": name,
                "ac_states": ac_states,
                "temp": temperature,
                "humidity": humidity,
                "target_temp": target_temperature,
                "hvac_mode": hvac_mode,
                "on": running,
                "fan_mode": fan_mode,
                "swing_mode": swing_mode,
                "horizontal_swing_mode": horizontal_swing_mode,
                "light_mode": light_mode,
                "available": available,
                "hvac_modes": hvac_modes,
                "fan_modes": fan_modes,
                "swing_modes": swing_modes,
                "horizontal_swing_modes": horizontal_swing_modes,
                "light_modes": light_modes,
                "temp_unit": temperature_unit_key,
                "temp_list": temperatures_list,
                "temp_step": temperature_step,
                "active_features": active_features,
                "full_features": full_features,
                "state": state,
                "fw_ver": fw_ver,
                "fw_type": fw_type,
                "model": model,
                "calibration_temp": calibration_temp,
                "calibration_hum": calibration_hum,
                "full_capabilities": capabilities,
                "motion_sensors": motion_sensors,
                "pure_sensitivity": pure_sensitivity,
                "pure_boost_enabled": pure_boost_enabled,
                "pm25": pm25,
            }

        return SensiboData(raw=data, parsed=device_data)
