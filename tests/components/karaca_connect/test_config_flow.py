"""Tests for the Karaca Connect config flow."""

from unittest.mock import AsyncMock, patch

from karaca_connect_client import KaracaAuthError, KaracaConnectionError
import pytest
from pytest_homeassistant.common import MockConfigEntry

from homeassistant.components.karaca_connect.const import DOMAIN
from homeassistant.config_entries import SOURCE_USER
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType, InvalidData

pytestmark = pytest.mark.usefixtures("mock_setup_entry")


async def test_invalid_login(hass: HomeAssistant) -> None:
    """Reject invalid credentials before creating an entry."""
    with patch(
        "homeassistant.components.karaca_connect.config_flow.KaracaClient",
        autospec=True,
    ) as client_class:
        client = client_class.return_value
        client.login = AsyncMock(side_effect=KaracaAuthError())
        client.get_devices = AsyncMock(return_value=[{"id": "device-123"}])
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": SOURCE_USER}
        )
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={"email": "example@example.invalid", "password": "wrong"},
        )
        assert result["type"] is FlowResultType.FORM
        assert result["errors"]["base"] == "invalid_auth"
        client.login.side_effect = None
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={"email": "example@example.invalid", "password": "correct"},
        )
        assert result["type"] is FlowResultType.CREATE_ENTRY
        assert result["result"].unique_id == "karaca_device-123"


async def test_duplicate_device(hass: HomeAssistant) -> None:
    """Do not allow a device to be configured twice."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id="karaca_device-123",
        title="Existing tea maker",
        data={},
    )
    entry.add_to_hass(hass)
    with patch(
        "homeassistant.components.karaca_connect.config_flow.KaracaClient",
        autospec=True,
    ) as client_class:
        client_class.return_value.login = AsyncMock()
        client_class.return_value.get_devices = AsyncMock(
            return_value=[{"id": "device-123", "label": "Kitchen"}]
        )
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": SOURCE_USER}
        )
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={"email": "example@example.invalid", "password": "placeholder"},
        )
        assert result["type"] is FlowResultType.ABORT
        assert result["reason"] == "already_configured"


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
        assert result["result"].unique_id == "karaca_device-123"


async def test_no_devices(hass: HomeAssistant) -> None:
    """No device is a validation error, not a success."""
    with patch(
        "homeassistant.components.karaca_connect.config_flow.KaracaClient",
        autospec=True,
    ) as client_class:
        client = client_class.return_value
        client.login = AsyncMock()
        client.get_devices = AsyncMock(return_value=[])
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
        client.get_devices.return_value = [{"id": "device-123"}]
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={
                "email": "example@example.invalid",
                "password": "not-a-real-password",
            },
        )
        assert result["type"] is FlowResultType.CREATE_ENTRY
        assert result["result"].unique_id == "karaca_device-123"


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
        assert result["result"].unique_id == "karaca_device-456"


async def test_cloud_failure_recovers(hass: HomeAssistant) -> None:
    """Allow retrying a temporary connection failure."""
    with patch(
        "homeassistant.components.karaca_connect.config_flow.KaracaClient",
        autospec=True,
    ) as client_class:
        client = client_class.return_value
        client.login = AsyncMock(side_effect=KaracaConnectionError())
        client.get_devices = AsyncMock(return_value=[{"id": "device-123"}])
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": SOURCE_USER}
        )
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={"email": "example@example.invalid", "password": "password"},
        )
        assert result["type"] is FlowResultType.FORM
        assert result["errors"]["base"] == "cannot_connect"

        client.login.side_effect = None
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={"email": "example@example.invalid", "password": "password"},
        )
        assert result["type"] is FlowResultType.CREATE_ENTRY
        assert result["result"].unique_id == "karaca_device-123"


async def test_invalid_device_selection_recovers(hass: HomeAssistant) -> None:
    """An invalid selection can be corrected within the same flow."""
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
            user_input={"email": "example@example.invalid", "password": "password"},
        )
        assert result["step_id"] == "select_device"
        with pytest.raises(InvalidData, match="Schema validation failed"):
            await hass.config_entries.flow.async_configure(
                result["flow_id"], user_input={"device_id": "missing"}
            )
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input={"device_id": "device-456"}
        )
        assert result["type"] is FlowResultType.CREATE_ENTRY
        assert result["result"].unique_id == "karaca_device-456"
