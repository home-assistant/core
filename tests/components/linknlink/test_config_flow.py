"""Tests for the LinknLink config flow."""

from dataclasses import replace
from unittest.mock import AsyncMock

from aiolinknlink import UltraConnectionError
import pytest
from pytest_homeassistant.common import MockConfigEntry

from homeassistant.components.linknlink.const import DISPLAY_MODEL, DOMAIN
from homeassistant.config_entries import SOURCE_USER, ConfigFlowResult
from homeassistant.const import CONF_HOST
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from .conftest import DEVICE, HOST, MAC, SESSION


async def _async_submit_host(hass: HomeAssistant, host: str) -> ConfigFlowResult:
    """Start a user flow and submit a host."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_USER},
    )
    assert result["type"] is FlowResultType.FORM
    return await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_HOST: host},
    )


@pytest.mark.usefixtures("mock_setup_entry")
async def test_full_flow(hass: HomeAssistant, mock_linknlink_client: AsyncMock) -> None:
    """Test the complete user flow."""
    mock_linknlink_client.connect.return_value = replace(
        SESSION, device=replace(DEVICE, model=DISPLAY_MODEL, port=1234)
    )
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_USER},
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_HOST: HOST},
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == DISPLAY_MODEL
    assert result["data"] == {CONF_HOST: HOST}
    assert result["result"].unique_id == MAC
    mock_linknlink_client.discover_host.assert_awaited_once_with(HOST)
    mock_linknlink_client.connect.assert_awaited_once()


@pytest.mark.usefixtures("mock_setup_entry")
async def test_hostname_is_resolved_before_storage(
    hass: HomeAssistant,
    mock_linknlink_client: AsyncMock,
) -> None:
    """Test that a hostname is accepted but the device IPv4 address is stored."""
    hostname = "ultra.local"

    result = await _async_submit_host(hass, hostname)

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"][CONF_HOST] == HOST
    assert result["result"].unique_id == MAC
    mock_linknlink_client.discover_host.assert_awaited_once_with(hostname)


@pytest.mark.usefixtures("mock_setup_entry")
@pytest.mark.parametrize(
    "error",
    [
        UltraConnectionError("offline"),
        OSError("network unreachable"),
        TimeoutError(),
        ValueError("invalid response"),
    ],
)
async def test_connection_error_can_recover(
    hass: HomeAssistant,
    mock_linknlink_client: AsyncMock,
    error: Exception,
) -> None:
    """Test a connection error and recovery."""
    mock_linknlink_client.discover_host.side_effect = error
    result = await _async_submit_host(hass, HOST)

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "cannot_connect"}

    mock_linknlink_client.discover_host.side_effect = None
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_HOST: HOST},
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY


@pytest.mark.usefixtures("mock_setup_entry")
async def test_unknown_error_can_recover(
    hass: HomeAssistant, mock_linknlink_client: AsyncMock
) -> None:
    """Test an unexpected error and recovery."""
    mock_linknlink_client.connect.side_effect = RuntimeError("unexpected")
    result = await _async_submit_host(hass, HOST)

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "unknown"}

    mock_linknlink_client.connect.side_effect = None
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_HOST: HOST},
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY


@pytest.mark.usefixtures("mock_setup_entry")
async def test_duplicate_device(
    hass: HomeAssistant,
    mock_linknlink_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test that the same device cannot be configured twice."""
    mock_config_entry.add_to_hass(hass)
    result = await _async_submit_host(hass, HOST)

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"
    assert mock_config_entry.data == {CONF_HOST: HOST}


@pytest.mark.usefixtures("mock_setup_entry")
async def test_existing_device_updates_host(
    hass: HomeAssistant,
    mock_linknlink_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test rediscovery of a configured device updates its host."""
    new_host = "192.0.2.2"
    new_device = replace(DEVICE, ip=new_host)
    mock_linknlink_client.discover_host.return_value = new_device
    mock_linknlink_client.connect.return_value = replace(SESSION, device=new_device)
    mock_config_entry.add_to_hass(hass)

    result = await _async_submit_host(hass, new_host)

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"
    assert mock_config_entry.data[CONF_HOST] == new_host


@pytest.mark.usefixtures("mock_setup_entry")
async def test_new_device_at_previous_host_of_configured_device(
    hass: HomeAssistant,
    mock_linknlink_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test a different device can be added at a host used by another entry."""
    other_mac = "02:00:00:00:00:02"
    other_device = replace(DEVICE, id=other_mac, mac=other_mac)
    mock_linknlink_client.discover_host.return_value = other_device
    mock_linknlink_client.connect.return_value = replace(SESSION, device=other_device)
    mock_config_entry.add_to_hass(hass)

    result = await _async_submit_host(hass, HOST)

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"] == {CONF_HOST: HOST}
    assert result["result"].unique_id == other_mac
