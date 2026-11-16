"""Config flow tests for Karaca Connect.

These tests are to be executed in Home Assistant Core's own test environment.
"""

from unittest.mock import AsyncMock, patch

from homeassistant.config_entries import SOURCE_USER
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from homeassistant.components.karaca_connect.const import DOMAIN


async def test_single_device_flow(hass: HomeAssistant) -> None:
    """A single available device can be selected without an extra form."""
    with patch(
        "homeassistant.components.karaca_connect.config_flow.KaracaClient",
        autospec=True,
    ) as client_class:
        client = client_class.return_value
        client.login = AsyncMock()
        client.get_devices = AsyncMock(
            return_value=[{"id": "device-123", "label": "Kitchen"}]
        )
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": SOURCE_USER}
        )
        assert result["type"] is FlowResultType.FORM
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={
                "email": "example@example.invalid",
                "password": "not-a-real-password",
            },
        )
        assert result["type"] is FlowResultType.CREATE_ENTRY
        assert result["data"]["device_id"] == "device-123"


async def test_no_devices(hass: HomeAssistant) -> None:
    """No device is a validation error, not a success."""
    with patch(
        "homeassistant.components.karaca_connect.config_flow.KaracaClient",
        autospec=True,
    ) as client_class:
        client_class.return_value.login = AsyncMock()
        client_class.return_value.get_devices = AsyncMock(return_value=[])
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": SOURCE_USER}
        )
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={
                "email": "example@example.invalid",
                "password": "not-a-real-password",
            },
        )
        assert result["type"] is FlowResultType.FORM
        assert result["errors"]["base"] == "no_devices"


async def test_multiple_devices_require_selection(hass: HomeAssistant) -> None:
    """Never choose the first of multiple devices implicitly."""
    with patch(
        "homeassistant.components.karaca_connect.config_flow.KaracaClient",
        autospec=True,
    ) as client_class:
        client = client_class.return_value
        client.login = AsyncMock()
        client.get_devices = AsyncMock(
            return_value=[
                {"id": "device-123", "label": "Kitchen"},
                {"id": "device-456", "label": "Office"},
            ]
        )
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": SOURCE_USER}
        )
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={
                "email": "example@example.invalid",
                "password": "not-a-real-password",
            },
        )
        assert result["type"] is FlowResultType.FORM
        assert result["step_id"] == "select_device"
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input={"device_id": "device-456"}
        )
        assert result["type"] is FlowResultType.CREATE_ENTRY
        assert result["data"]["device_id"] == "device-456"
