"""Test config flow for the TuneBlade Remote integration."""

from unittest.mock import AsyncMock

import pytest

from homeassistant.components.tuneblade_remote.const import DOMAIN
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType


@pytest.mark.asyncio
async def test_user_flow_success(hass: HomeAssistant, mock_tuneblade_api) -> None:
    """Test successful user-initiated config flow."""

    mock_tuneblade_api.async_get_data = AsyncMock(return_value=[{"id": "abc"}])

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": "user"},
        data={
            "host": "127.0.0.1",
            "port": 54412,
            "name": "TestDevice",
        },
    )

    assert result["type"] == FlowResultType.CREATE_ENTRY
    assert result["title"] == "TestDevice"
    assert result["data"] == {
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
        data={
            "host": "127.0.0.1",
            "port": 54412,
            "name": "TestDevice",
        },
    )

    assert result["type"] == FlowResultType.FORM
    assert result["errors"] == {"base": "cannot_connect"}


@pytest.mark.asyncio
async def test_zeroconf_flow_success(hass: HomeAssistant, mock_tuneblade_api) -> None:
    """Test successful zeroconf discovery flow."""

    mock_tuneblade_api.async_get_data = AsyncMock(return_value=[{"id": "abc"}])

    discovery_info = {
        "host": "127.0.0.1",
        "port": 54412,
        "name": "TestDevice@local",
        "type": "_http._tcp.local.",
        "properties": {},
    }

    # Start zeroconf flow
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": "zeroconf"},
        data=discovery_info,
    )

    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "confirm"

    # Confirm
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
