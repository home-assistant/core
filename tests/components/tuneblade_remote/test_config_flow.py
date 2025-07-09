"""Test config flow for the TuneBlade Remote integration."""

from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from homeassistant.components.tuneblade_remote.const import DOMAIN
from homeassistant.config_entries import SOURCE_USER, ConfigEntry, ConfigEntryState
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType


@pytest.mark.asyncio
async def test_user_flow_success(hass: HomeAssistant, mock_tuneblade_api) -> None:
    """Test successful user-initiated config flow."""
    mock_tuneblade_api.async_get_data = AsyncMock(return_value=[{"id": "abc"}])

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": "user"},
    )

    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "user"

    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={
            "host": "127.0.0.1",
            "port": 54412,
            "name": "TestDevice",
        },
    )

    assert result2["type"] == FlowResultType.CREATE_ENTRY
    assert result2["title"] == "TestDevice"
    assert result2["data"] == {
        "host": "127.0.0.1",
        "port": 54412,
        "name": "TestDevice",
    }


@pytest.mark.asyncio
async def test_user_flow_cannot_connect(
    hass: HomeAssistant, mock_tuneblade_api
) -> None:
    """Test user config flow with connection failure."""
    mock_tuneblade_api.async_get_data = AsyncMock(return_value=[])

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": "user"},
    )

    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "user"

    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={
            "host": "127.0.0.1",
            "port": 54412,
            "name": "TestDevice",
        },
    )

    assert result2["type"] == FlowResultType.FORM
    assert result2["errors"] == {"base": "cannot_connect"}


@pytest.mark.asyncio
async def test_zeroconf_flow_success(hass: HomeAssistant, mock_tuneblade_api) -> None:
    """Test successful zeroconf discovery flow."""
    mock_tuneblade_api.async_get_data = AsyncMock(return_value=[{"id": "abc"}])

    discovery_info = SimpleNamespace(
        host="127.0.0.1",
        port=54412,
        name="TestDevice@local",
        type="_http._tcp.local.",
        properties={},
    )

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": "zeroconf"},
        data=discovery_info,
    )

    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "confirm"

    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input={}
    )

    assert result2["type"] == FlowResultType.CREATE_ENTRY
    assert result2["title"] == "TestDevice"
    assert result2["data"] == {
        "host": "127.0.0.1",
        "port": 54412,
        "name": "TestDevice",
    }


@pytest.mark.asyncio
async def test_user_flow_duplicate_unique_id_aborts(
    hass: HomeAssistant, mock_tuneblade_api
) -> None:
    """Test flow aborts if unique_id already configured."""
    mock_tuneblade_api.async_get_data = AsyncMock(return_value=[{"id": "abc"}])

    existing_entry = ConfigEntry(
        version=1,
        domain=DOMAIN,
        title="TestDevice",
        data={
            "host": "127.0.0.1",
            "port": 54412,
            "name": "TestDevice",
        },
        source=SOURCE_USER,
        unique_id="TestDevice_127.0.0.1_54412",
        entry_id="12345",
        options={},
        discovery_info=None,
        disabled_by=None,
        reason=None,
        context=None,
        entry_type=None,
        sub_entries=[],
        minor_version=1,
        state=ConfigEntryState.LOADED,
    )
    hass.config_entries._entries.append(existing_entry)

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": "user"},
    )

    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "user"

    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={
            "host": "127.0.0.1",
            "port": 54412,
            "name": "TestDevice",
        },
    )

    assert result2["type"] == FlowResultType.ABORT
    assert result2["reason"] == "already_configured"
