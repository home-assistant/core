"""Test fixtures and config flow tests for the TuneBlade Remote integration."""

from unittest.mock import AsyncMock

import pytest

from homeassistant.components.tuneblade_remote import config_flow
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType


@pytest.mark.asyncio
async def test_user_flow_success(hass: HomeAssistant, mock_tuneblade_api) -> None:
    """Test successful manual config flow."""

    # Patch the async_get_data to return device list (mocked by fixture)
    mock_tuneblade_api.async_get_data = AsyncMock(return_value=[{"id": "abc"}])

    flow = config_flow.TuneBladeConfigFlow()
    flow.hass = hass

    result = await flow.async_step_user(
        {
            "host": "127.0.0.1",
            "port": 54412,
            "name": "TestDevice",
        }
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
    """Test manual config flow with connection failure."""

    mock_tuneblade_api.async_get_data = AsyncMock(return_value=[])
    flow = config_flow.TuneBladeConfigFlow()
    flow.hass = hass

    result = await flow.async_step_user(
        {
            "host": "127.0.0.1",
            "port": 54412,
            "name": "TestDevice",
        }
    )

    assert result["type"] == FlowResultType.FORM
    assert result["errors"] == {"base": "cannot_connect"}


@pytest.mark.asyncio
async def test_zeroconf_flow_success(hass: HomeAssistant, mock_tuneblade_api) -> None:
    """Test successful zeroconf discovery flow."""

    mock_tuneblade_api.async_get_data = AsyncMock(return_value=[{"id": "abc"}])

    flow = config_flow.TuneBladeConfigFlow()
    flow.hass = hass

    discovery_info = type(
        "DummyDiscoveryInfo",
        (),
        {"host": "127.0.0.1", "port": 54412, "name": "TestDevice@local"},
    )()

    # Start zeroconf flow, should go to confirm step
    result = await flow.async_step_zeroconf(discovery_info)
    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "confirm"

    # Confirm step to create entry
    result2 = await flow.async_step_confirm({})
    assert result2["type"] == FlowResultType.CREATE_ENTRY
    assert result2["title"] == "TestDevice"
    assert result2["data"] == {
        "host": "127.0.0.1",
        "port": 54412,
        "name": "TestDevice",
    }
