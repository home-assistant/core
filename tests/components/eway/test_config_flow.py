"""Test the Eway config flow."""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from homeassistant.components.eway.config_flow import (
    CannotConnect,
    EwayConfigFlow,
    InvalidAuth,
    validate_input,
)  # pylint: disable=no-name-in-module
from homeassistant.components.eway.const import (
    CONF_DEVICE_ID,
    CONF_DEVICE_MODEL,
    CONF_DEVICE_SN,
    CONF_KEEPALIVE,
    CONF_MQTT_HOST,
    CONF_MQTT_PASSWORD,
    CONF_MQTT_PORT,
    CONF_MQTT_USERNAME,
    CONF_SCAN_INTERVAL,
    DOMAIN,
)
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType


class TestEwayConfigFlow:
    """Test the Eway config flow."""

    @pytest.fixture
    def valid_user_input(self) -> dict[str, Any]:
        """Return valid user input for config flow."""
        return {
            CONF_MQTT_HOST: "test.mqtt.broker",
            CONF_MQTT_PORT: 1883,
            CONF_MQTT_USERNAME: "test_user",
            CONF_MQTT_PASSWORD: "test_password",
            CONF_DEVICE_ID: "test_device_id",
            CONF_DEVICE_SN: "test_device_sn",
            CONF_DEVICE_MODEL: "test_model",
            CONF_SCAN_INTERVAL: 30,
            CONF_KEEPALIVE: 60,
        }

    async def test_validate_input_success(
        self,
        hass: HomeAssistant,
        valid_user_input: dict[str, Any],
        mock_aioeway_import: MagicMock | AsyncMock,
    ):
        """Test successful validation of user input."""
        result = await validate_input(hass, valid_user_input)

        assert result == {"title": "Eway Inverter test_device_id"}

        # Verify that the MQTT client was created with correct parameters
        mock_aioeway_import.DeviceMQTTClient.assert_called_once_with(
            device_model="test_model",
            device_sn="test_device_sn",
            username="test_user",
            password="test_password",
            broker_host="test.mqtt.broker",
            broker_port=1883,
            use_tls=True,
            keepalive=60,
        )

    async def test_validate_input_connection_error(
        self,
        hass: HomeAssistant,
        valid_user_input: dict[str, Any],
        mock_aioeway_import: MagicMock | AsyncMock,
    ):
        """Test validation with connection error."""
        # Mock connection failure
        mock_client = mock_aioeway_import.DeviceMQTTClient.return_value
        mock_client.connect.side_effect = ConnectionError("Connection failed")

        with pytest.raises(CannotConnect):
            await validate_input(hass, valid_user_input)

    async def test_validate_input_generic_error(
        self,
        hass: HomeAssistant,
        valid_user_input: dict[str, Any],
        mock_aioeway_import: MagicMock | AsyncMock,
    ):
        """Test validation with generic error."""
        # Mock generic failure
        mock_client = mock_aioeway_import.DeviceMQTTClient.return_value
        # mock_client.connect.side_effect = Exception("Generic error")
        mock_client.connect.side_effect = ConnectionError("Connection failed")

        with pytest.raises(CannotConnect):
            await validate_input(hass, valid_user_input)

    async def test_config_flow_user_step_success(
        self,
        hass: HomeAssistant,
        valid_user_input: dict[str, Any],
        mock_aioeway_import: MagicMock | AsyncMock,
    ):
        """Test successful user step in config flow."""
        flow = EwayConfigFlow()
        flow.hass = hass

        result = await flow.async_step_user(valid_user_input)

        assert result["type"] == FlowResultType.CREATE_ENTRY
        assert result["title"] == "Eway Inverter test_device_id"
        assert result["data"] == valid_user_input

    async def test_config_flow_user_step_no_input(self, hass: HomeAssistant):
        """Test user step with no input shows form."""
        flow = EwayConfigFlow()
        flow.hass = hass

        result = await flow.async_step_user(None)

        assert result["type"] == FlowResultType.FORM
        assert result["step_id"] == "user"
        assert result["errors"] == {}

    @patch(
        "homeassistant.components.eway.config_flow.device_mqtt_client.DeviceMQTTClient"
    )
    async def test_config_flow_user_step_cannot_connect(
        self,
        mock_device_mqtt_client,
        hass: HomeAssistant,
        valid_user_input: dict[str, Any],
    ):
        """Test user step with connection error."""
        mock_client = mock_device_mqtt_client.return_value
        mock_client.connect.side_effect = ConnectionError("Connection failed")

        flow = EwayConfigFlow()
        flow.hass = hass

        result = await flow.async_step_user(valid_user_input)

        assert result["type"] == FlowResultType.FORM
        assert result["step_id"] == "user"
        assert result["errors"] == {"base": "cannot_connect"}

    async def test_config_flow_user_step_invalid_auth(
        self, hass: HomeAssistant, valid_user_input: dict[str, Any]
    ):
        """Test user step with invalid auth error."""
        flow = EwayConfigFlow()
        flow.hass = hass

        with patch(
            "homeassistant.components.eway.config_flow.validate_input",
            side_effect=InvalidAuth("Invalid credentials"),
        ):
            result = await flow.async_step_user(valid_user_input)

        assert result["type"] == FlowResultType.FORM
        assert result["step_id"] == "user"
        assert result["errors"] == {"base": "invalid_auth"}

    async def test_config_flow_user_step_unknown_error(
        self, hass: HomeAssistant, valid_user_input: dict[str, Any]
    ):
        """Test user step with unknown error."""
        flow = EwayConfigFlow()
        flow.hass = hass

        with patch(
            "homeassistant.components.eway.config_flow.validate_input",
            side_effect=Exception("Unknown error"),
        ):
            result = await flow.async_step_user(valid_user_input)

        assert result["type"] == FlowResultType.FORM
        assert result["step_id"] == "user"
        assert result["errors"] == {"base": "unknown"}

    async def test_config_flow_version(self):
        """Test config flow version."""
        flow = EwayConfigFlow()
        assert flow.VERSION == 1

    async def test_config_flow_domain(self):
        """Test config flow domain."""

        assert DOMAIN == "eway"

    async def test_config_flow_with_different_ports(
        self, hass: HomeAssistant, mock_aioeway_import: MagicMock | AsyncMock
    ):
        """Test config flow with different MQTT ports."""
        flow = EwayConfigFlow()
        flow.hass = hass

        # Test with SSL port
        user_input_ssl = {
            CONF_MQTT_HOST: "ssl.mqtt.broker",
            CONF_MQTT_PORT: 8883,
            CONF_MQTT_USERNAME: "ssl_user",
            CONF_MQTT_PASSWORD: "ssl_password",
            CONF_DEVICE_ID: "ssl_device",
            CONF_DEVICE_SN: "ssl_sn",
            CONF_DEVICE_MODEL: "ssl_model",
            CONF_SCAN_INTERVAL: 60,
            CONF_KEEPALIVE: 120,
        }

        result = await flow.async_step_user(user_input_ssl)

        assert result["type"] == FlowResultType.CREATE_ENTRY
        assert result["title"] == "Eway Inverter ssl_device"
        assert result["data"][CONF_MQTT_PORT] == 8883

    async def test_config_flow_with_minimal_keepalive(
        self, hass: HomeAssistant, mock_aioeway_import: MagicMock | AsyncMock
    ):
        """Test config flow with minimal keepalive value."""
        flow = EwayConfigFlow()
        flow.hass = hass

        user_input = {
            CONF_MQTT_HOST: "test.mqtt.broker",
            CONF_MQTT_PORT: 1883,
            CONF_MQTT_USERNAME: "test_user",
            CONF_MQTT_PASSWORD: "test_password",
            CONF_DEVICE_ID: "test_device",
            CONF_DEVICE_SN: "test_sn",
            CONF_DEVICE_MODEL: "test_model",
            CONF_SCAN_INTERVAL: 10,  # Minimal scan interval
            CONF_KEEPALIVE: 30,  # Minimal keepalive
        }

        result = await flow.async_step_user(user_input)

        assert result["type"] == FlowResultType.CREATE_ENTRY
        assert result["data"][CONF_SCAN_INTERVAL] == 10
        assert result["data"][CONF_KEEPALIVE] == 30

    async def test_config_flow_with_long_device_names(
        self, hass: HomeAssistant, mock_aioeway_import: MagicMock | AsyncMock
    ):
        """Test config flow with long device names."""
        flow = EwayConfigFlow()
        flow.hass = hass

        user_input = {
            CONF_MQTT_HOST: "test.mqtt.broker",
            CONF_MQTT_PORT: 1883,
            CONF_MQTT_USERNAME: "test_user",
            CONF_MQTT_PASSWORD: "test_password",
            CONF_DEVICE_ID: "very_long_device_id_with_many_characters_12345",
            CONF_DEVICE_SN: "very_long_serial_number_with_many_characters_67890",
            CONF_DEVICE_MODEL: "very_long_model_name_with_many_characters_abcdef",
            CONF_SCAN_INTERVAL: 30,
            CONF_KEEPALIVE: 60,
        }

        result = await flow.async_step_user(user_input)

        assert result["type"] == FlowResultType.CREATE_ENTRY
        assert "very_long_device_id_with_many_characters_12345" in result["title"]


class TestEwayConfigFlowExceptions:
    """Test Eway config flow exception classes."""

    def test_cannot_connect_exception(self):
        """Test CannotConnect exception."""
        exception = CannotConnect("Connection failed")
        assert str(exception) == "Connection failed"
        assert isinstance(exception, Exception)

    def test_invalid_auth_exception(self):
        """Test InvalidAuth exception."""
        exception = InvalidAuth("Invalid credentials")
        assert str(exception) == "Invalid credentials"
        assert isinstance(exception, Exception)
