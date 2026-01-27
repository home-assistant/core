"""Test the LibreHardwareMonitor config flow."""

from unittest.mock import AsyncMock

from librehardwaremonitor_api import (
    LibreHardwareMonitorConnectionError,
    LibreHardwareMonitorNoDevicesError,
    LibreHardwareMonitorUnauthorizedError,
)
import pytest

from homeassistant.components.libre_hardware_monitor.const import DOMAIN
from homeassistant.config_entries import SOURCE_USER
from homeassistant.const import CONF_HOST, CONF_PORT
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from .conftest import AUTH_INPUT, REAUTH_INPUT, VALID_CONFIG, VALID_CONFIG_WITH_AUTH

from tests.common import MockConfigEntry


async def test_create_entry_without_auth(
    hass: HomeAssistant,
    mock_setup_entry: AsyncMock,
    mock_lhm_client: AsyncMock,
) -> None:
    """Test that a complete config entry is created."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input=VALID_CONFIG
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["result"].unique_id is None

    created_config_entry = result["result"]
    assert (
        created_config_entry.title
        == f"GAMING-PC ({VALID_CONFIG[CONF_HOST]}:{VALID_CONFIG[CONF_PORT]})"
    )
    assert created_config_entry.data == VALID_CONFIG

    assert mock_setup_entry.call_count == 1


async def test_create_entry_with_auth(
    hass: HomeAssistant,
    mock_setup_entry: AsyncMock,
    mock_lhm_client: AsyncMock,
) -> None:
    """Test that a complete config entry is created with authentication credentials."""
    mock_lhm_client.get_data.side_effect = LibreHardwareMonitorUnauthorizedError()

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input=VALID_CONFIG
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reauth_confirm"

    mock_lhm_client.get_data.side_effect = None

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input=AUTH_INPUT
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["result"].unique_id is None

    created_config_entry = result["result"]
    assert created_config_entry.data == VALID_CONFIG_WITH_AUTH

    assert mock_setup_entry.call_count == 1


@pytest.mark.parametrize(
    ("side_effect", "error_text"),
    [
        (LibreHardwareMonitorConnectionError, "cannot_connect"),
        (LibreHardwareMonitorNoDevicesError, "no_devices"),
    ],
)
async def test_errors_and_flow_recovery(
    hass: HomeAssistant,
    mock_setup_entry: AsyncMock,
    mock_lhm_client: AsyncMock,
    side_effect: Exception,
    error_text: str,
) -> None:
    """Test that errors are shown as expected."""
    mock_lhm_client.get_data.side_effect = side_effect

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input=VALID_CONFIG
    )

    assert result["errors"] == {"base": error_text}
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"

    mock_lhm_client.get_data.side_effect = None

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input=VALID_CONFIG
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert mock_setup_entry.call_count == 1


async def test_lhm_server_already_exists_without_auth(
    hass: HomeAssistant, mock_setup_entry: AsyncMock, mock_config_entry: MockConfigEntry
) -> None:
    """Test we only allow a single entry per server."""
    mock_config_entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input=VALID_CONFIG
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"

    assert mock_setup_entry.call_count == 0


async def test_lhm_server_already_exists_with_auth(
    hass: HomeAssistant,
    mock_setup_entry: AsyncMock,
    mock_auth_config_entry: MockConfigEntry,
) -> None:
    """Test auth has no influence on single entry per server."""
    mock_auth_config_entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input=VALID_CONFIG
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"

    assert mock_setup_entry.call_count == 0


async def test_reauth_no_previous_credentials(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_lhm_client: AsyncMock,
) -> None:
    """Test reauth flow when web server did not require auth before."""
    mock_config_entry.add_to_hass(hass)

    result = await mock_config_entry.start_reauth_flow(hass)

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reauth_confirm"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        REAUTH_INPUT,
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reauth_successful"
    assert mock_config_entry.data == {**VALID_CONFIG, **REAUTH_INPUT}
    assert len(hass.config_entries.async_entries()) == 1


async def test_reauth_with_previous_credentials(
    hass: HomeAssistant,
    mock_auth_config_entry: MockConfigEntry,
    mock_lhm_client: AsyncMock,
) -> None:
    """Test reauth flow when web server credentials changed."""
    mock_auth_config_entry.add_to_hass(hass)

    result = await mock_auth_config_entry.start_reauth_flow(hass)

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reauth_confirm"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        REAUTH_INPUT,
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reauth_successful"
    assert mock_auth_config_entry.data == {**VALID_CONFIG, **REAUTH_INPUT}
    assert len(hass.config_entries.async_entries()) == 1


@pytest.mark.parametrize(
    ("side_effect", "error_text"),
    [
        (LibreHardwareMonitorConnectionError, "cannot_connect"),
        (LibreHardwareMonitorUnauthorizedError, "invalid_auth"),
        (LibreHardwareMonitorNoDevicesError, "no_devices"),
    ],
)
async def test_reauth_errors(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_lhm_client: AsyncMock,
    side_effect: Exception,
    error_text: str,
) -> None:
    """Test reauth flow errors."""
    mock_config_entry.add_to_hass(hass)

    result = await mock_config_entry.start_reauth_flow(hass)

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reauth_confirm"

    mock_lhm_client.get_data.side_effect = side_effect
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        REAUTH_INPUT,
    )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": error_text}

    mock_lhm_client.get_data.side_effect = None
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        REAUTH_INPUT,
    )

    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reauth_successful"
    assert mock_config_entry.data == {**VALID_CONFIG, **REAUTH_INPUT}
    assert len(hass.config_entries.async_entries()) == 1
