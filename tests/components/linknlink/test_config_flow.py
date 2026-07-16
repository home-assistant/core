"""Tests for the LinknLink config flow."""

from dataclasses import replace
from unittest.mock import AsyncMock

from aiolinknlink import UltraConnectionError
import pytest

from homeassistant.components.linknlink.const import DISPLAY_MODEL, DOMAIN
from homeassistant.config_entries import SOURCE_RECONFIGURE, SOURCE_USER
from homeassistant.const import CONF_HOST, CONF_MAC, CONF_PORT
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from .conftest import DEVICE, HOST, MAC, PORT, SESSION

from tests.common import MockConfigEntry


@pytest.mark.usefixtures("mock_setup_entry")
async def test_full_flow(hass: HomeAssistant, mock_linknlink_client: AsyncMock) -> None:
    """Test the complete user flow."""
    mock_linknlink_client.connect.return_value = replace(
        SESSION, device=replace(DEVICE, model=DISPLAY_MODEL)
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
    assert result["data"] == {CONF_HOST: HOST, CONF_MAC: MAC, CONF_PORT: PORT}
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

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_USER},
        data={CONF_HOST: hostname},
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"][CONF_HOST] == HOST
    mock_linknlink_client.discover_host.assert_awaited_once_with(hostname)


@pytest.mark.usefixtures("mock_setup_entry")
async def test_connection_error_can_recover(
    hass: HomeAssistant, mock_linknlink_client: AsyncMock
) -> None:
    """Test a connection error and recovery."""
    mock_linknlink_client.discover_host.side_effect = UltraConnectionError("offline")
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_USER},
        data={CONF_HOST: HOST},
    )

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
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_USER},
        data={CONF_HOST: HOST},
    )

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
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_USER},
        data={CONF_HOST: HOST},
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"
    mock_linknlink_client.discover_host.assert_not_awaited()
    mock_linknlink_client.connect.assert_not_awaited()


@pytest.mark.usefixtures("mock_setup_entry")
async def test_existing_device_updates_host(
    hass: HomeAssistant,
    mock_linknlink_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test rediscovery of a configured device updates its host."""
    new_host = "192.168.1.9"
    new_device = replace(DEVICE, ip=new_host)
    mock_linknlink_client.discover_host.return_value = new_device
    mock_linknlink_client.connect.return_value = replace(SESSION, device=new_device)
    mock_config_entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_USER},
        data={CONF_HOST: new_host},
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"
    assert mock_config_entry.data[CONF_HOST] == new_host


@pytest.mark.usefixtures("mock_setup_entry")
async def test_reconfigure(
    hass: HomeAssistant,
    mock_linknlink_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test changing the host of an existing device."""
    new_host = "192.168.1.9"
    new_device = replace(DEVICE, ip=new_host)
    mock_linknlink_client.discover_host.return_value = new_device
    mock_linknlink_client.connect.return_value = replace(SESSION, device=new_device)
    mock_config_entry.add_to_hass(hass)
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={
            "source": SOURCE_RECONFIGURE,
            "entry_id": mock_config_entry.entry_id,
        },
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reconfigure"
    assert result["description_placeholders"] == {"device_name": DISPLAY_MODEL}

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_HOST: new_host}
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reconfigure_successful"
    assert mock_config_entry.data == {
        CONF_HOST: new_host,
        CONF_MAC: MAC,
        CONF_PORT: PORT,
    }


@pytest.mark.usefixtures("mock_setup_entry")
@pytest.mark.parametrize(
    ("error", "expected_error"),
    [
        (UltraConnectionError("offline"), "cannot_connect"),
        (RuntimeError("unexpected"), "unknown"),
    ],
)
async def test_reconfigure_error_can_recover(
    hass: HomeAssistant,
    mock_linknlink_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
    error: Exception,
    expected_error: str,
) -> None:
    """Test a reconfiguration error and recovery."""
    new_host = "192.168.1.9"
    new_device = replace(DEVICE, ip=new_host)
    mock_linknlink_client.connect.return_value = replace(SESSION, device=new_device)
    mock_config_entry.add_to_hass(hass)
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={
            "source": SOURCE_RECONFIGURE,
            "entry_id": mock_config_entry.entry_id,
        },
    )
    mock_linknlink_client.discover_host.side_effect = error

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_HOST: new_host}
    )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": expected_error}

    mock_linknlink_client.discover_host.side_effect = None
    mock_linknlink_client.discover_host.return_value = new_device
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_HOST: new_host}
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reconfigure_successful"


@pytest.mark.usefixtures("mock_setup_entry")
async def test_reconfigure_rejects_wrong_device(
    hass: HomeAssistant,
    mock_linknlink_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test that reconfiguration cannot change the device identity."""
    other_mac = "e0:4b:41:01:67:bc"
    other_device = replace(
        DEVICE,
        id=other_mac,
        ip="192.168.1.9",
        mac=other_mac,
    )
    mock_linknlink_client.discover_host.return_value = other_device
    mock_linknlink_client.connect.return_value = replace(SESSION, device=other_device)
    mock_config_entry.add_to_hass(hass)
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={
            "source": SOURCE_RECONFIGURE,
            "entry_id": mock_config_entry.entry_id,
        },
    )

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_HOST: "192.168.1.9"}
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "wrong_device"
