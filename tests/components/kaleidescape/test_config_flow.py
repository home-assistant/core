"""Tests for Kaleidescape config flow."""

import dataclasses
from unittest.mock import MagicMock

import pytest

from homeassistant.components.kaleidescape.const import DOMAIN
from homeassistant.config_entries import SOURCE_SSDP, SOURCE_USER
from homeassistant.const import CONF_HOST
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from . import MOCK_HOST, MOCK_SSDP_DISCOVERY_INFO


@pytest.mark.usefixtures("mock_device")
async def test_user_config_flow_success(hass: HomeAssistant) -> None:
    """Test user config flow success."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input={CONF_HOST: MOCK_HOST}
    )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert "data" in result
    assert result["data"][CONF_HOST] == MOCK_HOST


async def test_user_config_flow_bad_connect_errors(
    hass: HomeAssistant, mock_device: MagicMock
) -> None:
    """Test errors when connection error occurs."""
    mock_device.connect.side_effect = ConnectionError

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}, data={CONF_HOST: MOCK_HOST}
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    assert result["errors"] == {"base": "cannot_connect"}


async def test_user_config_flow_unsupported_device_errors(
    hass: HomeAssistant, mock_device: MagicMock
) -> None:
    """Test errors when connecting to unsupported device."""
    mock_device.is_server_only = True

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}, data={CONF_HOST: MOCK_HOST}
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    assert result["errors"] == {"base": "unsupported"}


@pytest.mark.usefixtures("mock_device", "mock_integration")
async def test_user_config_flow_device_exists_abort(hass: HomeAssistant) -> None:
    """Test flow aborts when device already configured."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}, data={CONF_HOST: MOCK_HOST}
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


@pytest.mark.usefixtures("mock_device")
async def test_ssdp_config_flow_success(hass: HomeAssistant) -> None:
    """Test ssdp config flow success."""
    discovery_info = dataclasses.replace(MOCK_SSDP_DISCOVERY_INFO)
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_SSDP}, data=discovery_info
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "discovery_confirm"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input={}
    )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert "data" in result
    assert result["data"][CONF_HOST] == MOCK_HOST


async def test_ssdp_config_flow_bad_connect_aborts(
    hass: HomeAssistant, mock_device: MagicMock
) -> None:
    """Test abort when connection error occurs."""
    mock_device.connect.side_effect = ConnectionError

    discovery_info = dataclasses.replace(MOCK_SSDP_DISCOVERY_INFO)
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_SSDP}, data=discovery_info
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "cannot_connect"


async def test_ssdp_config_flow_unsupported_device_aborts(
    hass: HomeAssistant, mock_device: MagicMock
) -> None:
    """Test abort when connecting to unsupported device."""
    mock_device.is_server_only = True

    discovery_info = dataclasses.replace(MOCK_SSDP_DISCOVERY_INFO)
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_SSDP}, data=discovery_info
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "unsupported"
