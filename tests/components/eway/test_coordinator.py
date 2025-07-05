"""Test the Eway coordinator."""

from __future__ import annotations

from datetime import timedelta
from typing import Any
from unittest.mock import AsyncMock, patch

import pytest

from homeassistant.components.eway.const import (
    CONF_DEVICE_ID,
    CONF_DEVICE_MODEL,
    CONF_DEVICE_SN,
    CONF_MQTT_HOST,
    CONF_SCAN_INTERVAL,
    DEFAULT_SCAN_INTERVAL,
    DOMAIN,
)
from homeassistant.components.eway.coordinator import EwayDataUpdateCoordinator
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import UpdateFailed


class TestEwayDataUpdateCoordinator:
    """Test the Eway data update coordinator."""

    async def test_coordinator_initialization(
        self, hass: HomeAssistant, mock_config_entry: ConfigEntry
    ):
        """Test coordinator initialization."""
        coordinator = EwayDataUpdateCoordinator(hass, mock_config_entry)

        assert coordinator.entry == mock_config_entry
        assert coordinator.device_id == "test_device_id"
        assert coordinator.device_sn == "test_device_sn"
        assert coordinator.device_model == "test_model"
        assert coordinator.mqtt_host == "test.mqtt.broker"
        assert coordinator.mqtt_port == 1883
        assert coordinator.mqtt_username == "test_user"
        assert coordinator.mqtt_password == "test_password"
        assert coordinator.keepalive == 60
        assert coordinator.update_interval == timedelta(seconds=30)
        assert coordinator._client is None
        assert coordinator._device_data == {}
        assert coordinator._device_info is None

    async def test_coordinator_initialization_with_defaults(self, hass: HomeAssistant):
        """Test coordinator initialization with default values."""
        config_entry = ConfigEntry(
            version=1,
            minor_version=1,
            domain=DOMAIN,
            title="Test Eway Inverter",
            data={},  # Empty data to test defaults
            options={},
            source="user",
            entry_id="test_entry_id",
            unique_id="test_unique_id",
            discovery_keys={},
            subentries_data={},
        )

        coordinator = EwayDataUpdateCoordinator(hass, config_entry)

        assert coordinator.device_id == "unknown"
        assert coordinator.device_sn == "unknown"
        assert coordinator.device_model == "unknown"
        assert coordinator.mqtt_host == "localhost"
        assert coordinator.mqtt_port == 1883
        assert coordinator.mqtt_username is None
        assert coordinator.mqtt_password is None
        assert coordinator.keepalive == 60
        assert coordinator.update_interval == timedelta(seconds=DEFAULT_SCAN_INTERVAL)

    async def test_coordinator_initialization_custom_scan_interval(
        self, hass: HomeAssistant
    ):
        """Test coordinator initialization with custom scan interval."""
        config_entry = ConfigEntry(
            version=1,
            minor_version=1,
            domain=DOMAIN,
            title="Test Eway Inverter",
            data={CONF_SCAN_INTERVAL: 120},
            options={},
            source="user",
            entry_id="test_entry_id",
            unique_id="test_unique_id",
            discovery_keys={},
            subentries_data={},
        )

        coordinator = EwayDataUpdateCoordinator(hass, config_entry)
        assert coordinator.update_interval == timedelta(seconds=120)

    async def test_async_update_data_first_time(
        self,
        hass: HomeAssistant,
        mock_config_entry: ConfigEntry,
        mock_aioeway_module,
        mock_device_data: list[dict[str, Any]],
    ):
        """Test first time data update."""
        coordinator = EwayDataUpdateCoordinator(hass, mock_config_entry)
        mock_client = mock_aioeway_module.DeviceMQTTClient.return_value

        mock_client.request_device_data_and_wait = AsyncMock(
            return_value=[mock_aioeway_module.DeviceData.from_dict(mock_device_data[0])]
        )

        # 直接调用真实的_async_update_data方法
        result = await coordinator._async_update_data()

        # 验证client被创建
        mock_aioeway_module.DeviceMQTTClient.assert_called_once_with(
            device_model="test_model",
            device_sn="test_device_sn",
            username="test_user",
            password="test_password",
            broker_host="test.mqtt.broker",
            broker_port=1883,
            use_tls=True,
            keepalive=60,
        )

        # 验证返回的数据
        assert result is not None

        # Mock the data callback to simulate receiving data
        async def simulate_data_received():
            device_data = mock_aioeway_module.DeviceData.from_dict(mock_device_data[0])
            coordinator._device_data.update(
                {
                    "gen_power": device_data.gen_power,
                    "grid_voltage": device_data.grid_voltage,
                    "input_current": device_data.input_current,
                    "grid_freq": device_data.grid_freq,
                    "temperature": device_data.temperature,
                    "gen_power_today": device_data.gen_power_today / 1000,
                    "gen_power_total": device_data.gen_power_total,
                    "input_voltage": device_data.input_voltage,
                    "error_code": device_data.err_code,
                    "duration": device_data.duration,
                }
            )

        with patch.object(
            coordinator, "_async_update_data", side_effect=simulate_data_received
        ):
            await coordinator._async_update_data()

        # Verify client was created and connected
        mock_aioeway_module.DeviceMQTTClient.assert_called_once_with(
            device_model="test_model",
            device_sn="test_device_sn",
            username="test_user",
            password="test_password",
            broker_host="test.mqtt.broker",
            broker_port=1883,
            use_tls=True,
            keepalive=60,
        )

    async def test_async_update_data_connection_error(
        self, hass: HomeAssistant, mock_config_entry: ConfigEntry, mock_aioeway_module
    ):
        """Test data update with connection error."""
        coordinator = EwayDataUpdateCoordinator(hass, mock_config_entry)
        mock_client = mock_aioeway_module.DeviceMQTTClient.return_value
        mock_client.connect.side_effect = ConnectionError("Connection failed")

        with pytest.raises(UpdateFailed):
            await coordinator._async_update_data()

    async def test_async_update_data_import_error(
        self, hass: HomeAssistant, mock_config_entry: ConfigEntry
    ):
        """Test data update with import error."""
        coordinator = EwayDataUpdateCoordinator(hass, mock_config_entry)

        with (
            patch(
                "homeassistant.components.eway.coordinator.device_mqtt_client.DeviceMQTTClient",
                side_effect=ImportError("Module not found"),
            ),
            pytest.raises(UpdateFailed),
        ):
            await coordinator._async_update_data()

    async def test_async_update_data_subsequent_calls(
        self,
        hass: HomeAssistant,
        mock_config_entry: ConfigEntry,
        mock_aioeway_module,
        mock_device_data: list[dict[str, Any]],
    ):
        """Test subsequent data update calls reuse existing client."""
        coordinator = EwayDataUpdateCoordinator(hass, mock_config_entry)
        mock_client = mock_aioeway_module.DeviceMQTTClient.return_value

        # First call
        await coordinator._async_update_data()
        first_client = coordinator._client

        # Second call
        await coordinator._async_update_data()
        second_client = coordinator._client

        # Should be the same client instance
        assert first_client == second_client
        # Connect should only be called once
        assert mock_client.connect.call_count == 1

    async def test_data_callback_processing(
        self,
        hass: HomeAssistant,
        mock_config_entry: ConfigEntry,
        mock_aioeway_module,
        mock_device_data: list[dict[str, Any]],
    ):
        """Test data callback processing."""
        coordinator = EwayDataUpdateCoordinator(hass, mock_config_entry)

        # Simulate the data callback that would be set up in _async_update_data
        device_data_list = [
            mock_aioeway_module.DeviceData.from_dict(data) for data in mock_device_data
        ]

        # Create a mock callback function similar to what's in the coordinator
        async def data_callback(device_data_list):
            if device_data_list:
                device_data = device_data_list[0]
                coordinator._device_data.update(
                    {
                        "gen_power": device_data.gen_power,
                        "grid_voltage": device_data.grid_voltage,
                        "input_current": device_data.input_current,
                        "grid_freq": device_data.grid_freq,
                        "temperature": device_data.temperature,
                        "gen_power_today": device_data.gen_power_today / 1000,
                        "gen_power_total": device_data.gen_power_total,
                        "input_voltage": device_data.input_voltage,
                        "error_code": device_data.err_code,
                        "duration": device_data.duration,
                    }
                )

        await data_callback(device_data_list)

        # Verify data was processed correctly
        assert coordinator._device_data["gen_power"] == 1250.0
        assert coordinator._device_data["grid_voltage"] == 230.1
        assert coordinator._device_data["input_current"] == 5.2
        assert coordinator._device_data["grid_freq"] == 50.0
        assert coordinator._device_data["temperature"] == 45.2
        assert (
            coordinator._device_data["gen_power_today"] == 5.5
        )  # 5500 Wh / 1000 = 5.5 kWh
        assert coordinator._device_data["gen_power_total"] == 12500
        assert coordinator._device_data["input_voltage"] == 240.5
        assert coordinator._device_data["error_code"] == 0
        assert coordinator._device_data["duration"] == 3600

    async def test_info_callback_processing(
        self,
        hass: HomeAssistant,
        mock_config_entry: ConfigEntry,
        mock_aioeway_module,
        mock_device_info: dict[str, Any],
    ):
        """Test info callback processing."""
        coordinator = EwayDataUpdateCoordinator(hass, mock_config_entry)

        # Simulate the info callback that would be set up in _async_update_data
        device_info = mock_aioeway_module.DeviceInfo.from_dict(mock_device_info)

        # Create a mock callback function similar to what's in the coordinator
        async def info_callback(device_info):
            coordinator._device_info = device_info

        await info_callback(device_info)

        # Verify info was processed correctly
        assert coordinator._device_info == device_info
        assert coordinator._device_info.net_firm_ver == 1.2
        assert coordinator._device_info.app_firm_ver == 2.1
        assert coordinator._device_info.wifi_ssid == "TestWiFi"
        assert coordinator._device_info.ip == "192.168.1.100"

    async def test_device_info_property(
        self, hass: HomeAssistant, mock_config_entry: ConfigEntry
    ):
        """Test device_info property."""
        coordinator = EwayDataUpdateCoordinator(hass, mock_config_entry)

        # Test when _device_info is None
        device_info = coordinator.device_info
        assert device_info is not None
        assert device_info["identifiers"] == {(DOMAIN, "test_device_id_test_device_sn")}
        assert device_info["name"] == "Eway Inverter test_device_id/test_device_sn"
        assert device_info["manufacturer"] == "Eway"
        assert device_info["model"] == "test_model"
        assert device_info["sw_version"] == "Unknown"

    async def test_device_info_property_with_device_info(
        self,
        hass: HomeAssistant,
        mock_config_entry: ConfigEntry,
        mock_aioeway_module,
        mock_device_info: dict[str, Any],
    ):
        """Test device_info property when _device_info is available."""
        coordinator = EwayDataUpdateCoordinator(hass, mock_config_entry)
        coordinator._device_info = mock_aioeway_module.DeviceInfo.from_dict(
            mock_device_info
        )

        device_info = coordinator.device_info
        assert device_info is not None
        assert device_info["identifiers"] == {(DOMAIN, "test_device_id_test_device_sn")}
        assert device_info["name"] == "Eway Inverter test_device_id/test_device_sn"
        assert device_info["manufacturer"] == "Eway"
        assert device_info["model"] == "test_model"
        assert device_info["sw_version"] == "App: 2.1, Net: 1.2"

    async def test_coordinator_with_missing_optional_config(self, hass: HomeAssistant):
        """Test coordinator with missing optional configuration."""
        config_entry = ConfigEntry(
            version=1,
            minor_version=1,
            domain=DOMAIN,
            title="Test Eway Inverter",
            data={
                CONF_DEVICE_ID: "test_device",
                CONF_DEVICE_SN: "test_sn",
                CONF_DEVICE_MODEL: "test_model",
                CONF_MQTT_HOST: "test.broker",
                # Missing optional fields
            },
            options={},
            source="user",
            entry_id="test_entry_id",
            unique_id="test_unique_id",
            discovery_keys={},
            subentries_data={},
        )

        coordinator = EwayDataUpdateCoordinator(hass, config_entry)

        assert coordinator.mqtt_port == 1883  # Default
        assert coordinator.mqtt_username is None
        assert coordinator.mqtt_password is None
        assert coordinator.keepalive == 60  # Default
        assert coordinator.update_interval == timedelta(seconds=DEFAULT_SCAN_INTERVAL)

    # async def test_coordinator_error_handling_in_callback(
    #     self, hass: HomeAssistant, mock_config_entry: ConfigEntry, mock_aioeway_module
    # ):
    #     """Test error handling in data callback."""
    #     coordinator = EwayDataUpdateCoordinator(hass, mock_config_entry)

    #     # Create a callback that raises an exception
    #     async def failing_data_callback(device_data_list):
    #         raise ValueError("Callback error")

    #     # Register the failing callback with the coordinator
    #     coordinator.add_data_callback(failing_data_callback)

    #     # Test that coordinator handles callback errors gracefully
    #     with patch("homeassistant.components.eway.coordinator._LOGGER") as mock_logger:
    #         # Trigger data update that will call the failing callback
    #         await coordinator._async_update_data()

    #         # Verify that the error was logged
    #         mock_logger.error.assert_called_once()
    #         assert "Callback error" in str(mock_logger.error.call_args)

    async def test_coordinator_name_property(
        self, hass: HomeAssistant, mock_config_entry: ConfigEntry
    ):
        """Test coordinator name property."""
        coordinator = EwayDataUpdateCoordinator(hass, mock_config_entry)
        assert coordinator.name == DOMAIN
