"""Data update coordinator for Eway integration."""

from __future__ import annotations

from datetime import datetime, timedelta
import logging
from typing import Any

# from aioeway import device_mqtt_client
from aioeway import device_mqtt_client

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import (
    CONF_DEVICE_ID,
    CONF_DEVICE_MODEL,
    CONF_DEVICE_SN,
    CONF_KEEPALIVE,
    CONF_MQTT_HOST,
    CONF_MQTT_PASSWORD,
    CONF_MQTT_PORT,
    CONF_MQTT_USERNAME,
    CONF_SCAN_INTERVAL,
    DEFAULT_SCAN_INTERVAL,
    DOMAIN,
)

_LOGGER = logging.getLogger(__name__)


class EwayDataUpdateCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    """Class to manage fetching data from Eway device."""

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        """Initialize the coordinator."""
        self.entry = entry
        self.device_id = entry.data.get(CONF_DEVICE_ID, "unknown")
        self.device_sn = entry.data.get(CONF_DEVICE_SN, "unknown")
        self.device_model = entry.data.get(CONF_DEVICE_MODEL, "unknown")

        # MQTT configuration
        self.mqtt_host = entry.data.get(CONF_MQTT_HOST, "localhost")
        self.mqtt_port = entry.data.get(CONF_MQTT_PORT, 1883)
        self.mqtt_username = entry.data.get(CONF_MQTT_USERNAME)
        self.mqtt_password = entry.data.get(CONF_MQTT_PASSWORD)
        self.keepalive = entry.data.get(CONF_KEEPALIVE, 60)

        scan_interval = entry.data.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL)

        self.last_update_success_time: datetime | None = None

        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=timedelta(seconds=scan_interval),
        )

        self._client: device_mqtt_client.DeviceMQTTClient | None = None
        self._device_data: dict[str, Any] = {}
        self._device_info: device_mqtt_client.DeviceInfo | None = None

    async def _async_update_data(self) -> dict[str, Any]:
        """Fetch data from Eway device."""
        try:
            # Import aioeway here to avoid import errors if not installed
            # import aioeway

            if self._client is None:
                self._client = device_mqtt_client.DeviceMQTTClient(
                    device_model=self.device_model,
                    device_sn=self.device_sn,
                    username=self.mqtt_username,
                    password=self.mqtt_password,
                    broker_host=self.mqtt_host,
                    broker_port=self.mqtt_port,
                    use_tls=True,
                    keepalive=self.keepalive,
                )
                await self._client.connect()

                # Set up data callback
                async def data_callback(
                    device_data_list: list[device_mqtt_client.DeviceData],
                ):
                    if device_data_list:
                        # Use the first device data (assuming single device)
                        device_data = device_data_list[0]
                        self._device_data.update(
                            {
                                "gen_power": device_data.gen_power,
                                "grid_voltage": device_data.grid_voltage,
                                "input_current": device_data.input_current,
                                "grid_freq": device_data.grid_freq,
                                "temperature": device_data.temperature,
                                "gen_power_today": device_data.gen_power_today
                                / 1000,  # Convert Wh to kWh
                                "gen_power_total": device_data.gen_power_total,  # Already in kWh
                                "input_voltage": device_data.input_voltage,
                                "error_code": device_data.err_code,
                                "duration": device_data.duration,
                            }
                        )
                        _LOGGER.debug("Updated device data: %s", self._device_data)

                # Set up info callback
                async def info_callback(device_info: device_mqtt_client.DeviceInfo):
                    self._device_info = device_info
                    _LOGGER.debug("Updated device info: %s", device_info)

                # Start monitoring
                await self._client.start_monitoring(
                    device_id=self.device_id,
                    device_sn=self.device_sn,
                    data_callback=data_callback,
                    info_callback=info_callback,
                    data_interval=60,
                )

            # Request fresh data
            device_data_list = await self._client.request_device_data_and_wait(
                self.device_id, self.device_sn, timeout=10.0
            )

            if device_data_list:
                device_data = device_data_list[0]
                self._device_data.update(
                    {
                        "gen_power": device_data.gen_power,
                        "grid_voltage": device_data.grid_voltage,
                        "input_current": device_data.input_current,
                        "grid_freq": device_data.grid_freq,
                        "temperature": device_data.temperature,
                        "gen_power_today": device_data.gen_power_today
                        / 1000,  # Convert Wh to kWh
                        "gen_power_total": device_data.gen_power_total,  # Already in kWh
                        "input_voltage": device_data.input_voltage,
                        "error_code": device_data.err_code,
                        "duration": device_data.duration,
                    }
                )
                _LOGGER.debug("Updated device data: %s", self._device_data)
                return self._device_data
            return {}  # noqa: TRY300

        except Exception as err:
            _LOGGER.error("Error communicating with Eway device: %s", err)
            raise UpdateFailed(f"Error communicating with device: {err}") from err

    async def async_shutdown(self) -> None:
        """Shutdown the coordinator."""
        if self._client:
            await self._client.disconnect()
            self._client = None

    @property
    def device_info(self) -> DeviceInfo:
        """Return device information."""
        sw_version = "Unknown"
        if self._device_info:
            sw_version = f"App: {self._device_info.app_firm_ver}, Net: {self._device_info.net_firm_ver}"

        return DeviceInfo(
            identifiers={(DOMAIN, f"{self.device_id}_{self.device_sn}")},
            name=f"Eway Inverter {self.device_id}/{self.device_sn}",
            manufacturer="Eway",
            model=self.device_model,
            sw_version=sw_version,
        )

    @property
    def client_connected(self) -> bool:
        """Return True if MQTT client is connected."""
        return self._client is not None
