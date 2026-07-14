"""Tests for the LinknLink config flow."""

from dataclasses import replace
from unittest.mock import AsyncMock

from aiolinknlink import DISPLAY_MODEL_ULTRA2, UltraConnectionError
import pytest

from homeassistant.components.linknlink.const import DOMAIN
from homeassistant.config_entries import SOURCE_USER
from homeassistant.const import CONF_HOST, CONF_MAC, CONF_PORT
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from .conftest import DEVICE, HOST, MAC, PORT, SESSION

from tests.common import MockConfigEntry


@pytest.mark.usefixtures("mock_setup_entry")
async def test_full_flow(hass: HomeAssistant, mock_linknlink_client: AsyncMock) -> None:
    """Test the complete user flow."""
    mock_linknlink_client.connect.return_value = replace(
        SESSION, device=replace(DEVICE, model=DISPLAY_MODEL_ULTRA2)
    )
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_USER},
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_HOST: HOST, CONF_MAC: "E04B410167BB", CONF_PORT: PORT},
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == DISPLAY_MODEL_ULTRA2
    assert result["data"] == {CONF_HOST: HOST, CONF_MAC: MAC, CONF_PORT: PORT}
    assert result["result"].unique_id == MAC
    mock_linknlink_client.connect.assert_awaited_once()


@pytest.mark.usefixtures("mock_setup_entry")
async def test_connection_error_can_recover(
    hass: HomeAssistant, mock_linknlink_client: AsyncMock
) -> None:
    """Test a connection error and recovery."""
    mock_linknlink_client.connect.side_effect = UltraConnectionError("offline")
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_USER},
        data={CONF_HOST: HOST, CONF_MAC: MAC, CONF_PORT: PORT},
    )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "cannot_connect"}

    mock_linknlink_client.connect.side_effect = None
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_HOST: HOST, CONF_MAC: MAC, CONF_PORT: PORT},
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
        data={CONF_HOST: HOST, CONF_MAC: MAC, CONF_PORT: PORT},
    )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "unknown"}

    mock_linknlink_client.connect.side_effect = None
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_HOST: HOST, CONF_MAC: MAC, CONF_PORT: PORT},
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY


async def test_invalid_mac(hass: HomeAssistant) -> None:
    """Test that an invalid MAC address is rejected."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_USER},
        data={CONF_HOST: HOST, CONF_MAC: "not-a-mac", CONF_PORT: PORT},
    )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {CONF_MAC: "invalid_mac"}


@pytest.mark.usefixtures("mock_setup_entry")
async def test_duplicate_device(
    hass: HomeAssistant,
    mock_linknlink_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test that the same device cannot be configured twice."""
    mock_config_entry.add_to_hass(hass)
    mock_linknlink_client.connect.side_effect = UltraConnectionError("offline")
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_USER},
        data={CONF_HOST: HOST, CONF_MAC: MAC, CONF_PORT: PORT},
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"
    mock_linknlink_client.connect.assert_not_awaited()
