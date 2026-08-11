"""Test the PTDevices config flow."""

from unittest.mock import AsyncMock

from aioptdevices import PTDevicesRequestError, PTDevicesUnauthorizedError
from aioptdevices.interface import PTDevicesResponse
import pytest

from homeassistant.components.ptdevices.const import DOMAIN
from homeassistant.config_entries import SOURCE_USER
from homeassistant.const import CONF_API_TOKEN
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from tests.common import MockConfigEntry


async def test_flow_success(
    hass: HomeAssistant,
    mock_ptdevices_interface: AsyncMock,
    mock_ptdevices_setup_entry: AsyncMock,
) -> None:
    """Test a successful creation of config entries via user configuration."""

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_USER},
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_API_TOKEN: "test-api-token"},
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "User Name"
    assert result["result"].unique_id == "1234"
    assert result["data"] == {
        CONF_API_TOKEN: "test-api-token",
    }

    assert len(mock_ptdevices_interface.mock_calls) == 1


async def test_flow_duplicate_device(
    hass: HomeAssistant,
    mock_ptdevices_interface: AsyncMock,
    mock_ptdevices_setup_entry: AsyncMock,
    mock_ptdevices_config_entry: MockConfigEntry,
) -> None:
    """Test a duplicate config flow."""
    mock_ptdevices_config_entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_USER},
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_API_TOKEN: "test-api-token"},
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


@pytest.mark.parametrize(
    ("exception", "error"),
    [
        (PTDevicesUnauthorizedError, "invalid_access_token"),
        (PTDevicesRequestError, "cannot_connect"),
        (Exception, "unknown"),
    ],
)
async def test_flow_errors(
    hass: HomeAssistant,
    mock_ptdevices_interface: AsyncMock,
    mock_ptdevices_setup_entry: AsyncMock,
    exception: Exception,
    error: str,
) -> None:
    """Test flow errors."""
    mock_ptdevices_interface.get_data.side_effect = exception

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_USER},
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_API_TOKEN: "test-api-token"},
    )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": error}

    mock_ptdevices_interface.get_data.side_effect = None

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_API_TOKEN: "test-api-token"},
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY


async def test_flow_no_devices(
    hass: HomeAssistant,
    mock_ptdevices_interface: AsyncMock,
    mock_ptdevices_setup_entry: AsyncMock,
    mock_ptdevices_level: PTDevicesResponse,
) -> None:
    """Test A flow with no devices in the account."""

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_USER},
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"

    # No devices
    mock_ptdevices_interface.get_data.return_value = PTDevicesResponse(
        code=200,
        body={},
    )

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_API_TOKEN: "test-api-token"},
    )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "no_devices_found"}

    # Reset the mock to the default return value
    mock_ptdevices_interface.get_data.return_value = mock_ptdevices_level

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_API_TOKEN: "test-api-token"},
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
