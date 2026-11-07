"""Tests for the TrueNAS config flow."""

from dataclasses import replace
from unittest.mock import AsyncMock, MagicMock

from aiotruenas import (
    TrueNASAuthenticationError,
    TrueNASCallError,
    TrueNASConnectionRefusedError,
    TrueNASMalformedResponseError,
)
import pytest
from pytest_homeassistant.common import MockConfigEntry

from homeassistant.components.truenas_ce.const import DOMAIN
from homeassistant.config_entries import SOURCE_USER
from homeassistant.const import CONF_API_KEY, CONF_HOST, CONF_VERIFY_SSL
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from .const import SYSTEM_ID, SYSTEM_INFO

USER_INPUT = {
    CONF_HOST: "192.168.1.10",
    CONF_API_KEY: "1-abcdef",
    CONF_VERIFY_SSL: False,
}


@pytest.mark.usefixtures("mock_setup_entry")
async def test_full_flow(
    hass: HomeAssistant,
    mock_truenas_client: MagicMock,
    mock_truenas_system: AsyncMock,
) -> None:
    """Test the full user flow."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    assert result["errors"] == {}

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], USER_INPUT
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "truenas"
    assert result["data"] == USER_INPUT
    assert result["result"].unique_id == SYSTEM_ID
    mock_truenas_client.assert_called_once_with(
        "192.168.1.10", "1-abcdef", verify_ssl=False
    )
    mock_truenas_client.return_value.close.assert_awaited_once()


@pytest.mark.usefixtures("mock_setup_entry", "mock_truenas_client")
async def test_title_falls_back_to_host(
    hass: HomeAssistant, mock_truenas_system: AsyncMock
) -> None:
    """Test the host is the title when TrueNAS reports no hostname."""
    mock_truenas_system.get_system_info.return_value = replace(
        SYSTEM_INFO, hostname=None
    )
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], USER_INPUT
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "192.168.1.10"
    assert result["result"].unique_id == SYSTEM_ID


@pytest.mark.usefixtures("mock_setup_entry")
@pytest.mark.parametrize(
    ("exception", "error"),
    [
        (TrueNASAuthenticationError("rejected"), "invalid_auth"),
        (TrueNASCallError("denied", errname="EACCES"), "permission_denied"),
        (TrueNASCallError("failed", errname="EFAULT"), "cannot_connect"),
        (TrueNASConnectionRefusedError("refused"), "cannot_connect"),
        (TrueNASMalformedResponseError("malformed"), "cannot_connect"),
        (RuntimeError("boom"), "unknown"),
    ],
)
async def test_flow_errors(
    hass: HomeAssistant,
    mock_truenas_client: MagicMock,
    mock_truenas_system: AsyncMock,
    exception: Exception,
    error: str,
) -> None:
    """Test errors during the user step and the recovery from them."""
    mock_truenas_system.get_system_id.side_effect = exception
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], USER_INPUT
    )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": error}
    # The connection is closed on failure as well.
    mock_truenas_client.return_value.close.assert_awaited_once()

    mock_truenas_system.get_system_id.side_effect = None
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], USER_INPUT
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY


@pytest.mark.usefixtures("mock_setup_entry", "mock_truenas_system")
async def test_flow_invalid_host(
    hass: HomeAssistant, mock_truenas_client: MagicMock
) -> None:
    """Test a host with a scheme or path is rejected."""
    mock_truenas_client.side_effect = ValueError("host must not contain a scheme")
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {**USER_INPUT, CONF_HOST: "https://192.168.1.10"}
    )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {CONF_HOST: "invalid_host"}

    mock_truenas_client.side_effect = None
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], USER_INPUT
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY


@pytest.mark.usefixtures("mock_truenas_client", "mock_truenas_system")
async def test_flow_already_configured_host(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Test a host that is already configured is aborted."""
    mock_config_entry.add_to_hass(hass)
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], USER_INPUT
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


@pytest.mark.usefixtures("mock_truenas_client", "mock_truenas_system")
async def test_flow_already_configured_system(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Test the same system under another host name is aborted."""
    mock_config_entry.add_to_hass(hass)
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {**USER_INPUT, CONF_HOST: "truenas.local"}
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


@pytest.mark.usefixtures("mock_setup_entry", "mock_truenas_system")
async def test_reauth_flow(
    hass: HomeAssistant,
    mock_truenas_client: MagicMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test entering a new API key."""
    mock_config_entry.add_to_hass(hass)
    result = await mock_config_entry.start_reauth_flow(hass)
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reauth_confirm"
    assert result["errors"] == {}
    assert result["description_placeholders"] == {"name": "truenas"}

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_API_KEY: "2-new"}
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reauth_successful"
    assert mock_config_entry.data == {**USER_INPUT, CONF_API_KEY: "2-new"}
    mock_truenas_client.assert_called_with("192.168.1.10", "2-new", verify_ssl=False)
    mock_truenas_client.return_value.close.assert_awaited_once()


@pytest.mark.usefixtures("mock_setup_entry", "mock_truenas_client")
@pytest.mark.parametrize(
    ("exception", "error"),
    [
        (TrueNASAuthenticationError("rejected"), "invalid_auth"),
        (TrueNASCallError("denied", errname="EACCES"), "permission_denied"),
        (TrueNASConnectionRefusedError("refused"), "cannot_connect"),
        (RuntimeError("boom"), "unknown"),
    ],
)
async def test_reauth_flow_errors(
    hass: HomeAssistant,
    mock_truenas_system: AsyncMock,
    mock_config_entry: MockConfigEntry,
    exception: Exception,
    error: str,
) -> None:
    """Test errors while entering a new API key and the recovery from them."""
    mock_config_entry.add_to_hass(hass)
    result = await mock_config_entry.start_reauth_flow(hass)

    mock_truenas_system.get_system_id.side_effect = exception
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_API_KEY: "2-new"}
    )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": error}

    mock_truenas_system.get_system_id.side_effect = None
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_API_KEY: "2-new"}
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reauth_successful"
    assert mock_config_entry.data[CONF_API_KEY] == "2-new"


@pytest.mark.usefixtures("mock_setup_entry")
async def test_reauth_flow_other_system(
    hass: HomeAssistant,
    mock_truenas_client: MagicMock,
    mock_truenas_system: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test a host that now belongs to another system is aborted."""
    mock_config_entry.add_to_hass(hass)
    result = await mock_config_entry.start_reauth_flow(hass)

    mock_truenas_system.get_system_id.return_value = "another-system-id"
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_API_KEY: "2-new"}
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "unique_id_mismatch"
    assert mock_config_entry.data[CONF_API_KEY] == "1-abcdef"
    mock_truenas_client.return_value.close.assert_awaited_once()
