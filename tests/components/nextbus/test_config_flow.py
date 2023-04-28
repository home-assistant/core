"""Test the NextBus config flow."""

from collections.abc import Generator
from unittest.mock import MagicMock, patch

import pytest

from homeassistant import config_entries, setup
from homeassistant.components.nextbus.const import (
    CONF_AGENCY_NAME,
    CONF_ROUTE_NAME,
    CONF_STOP_NAME,
    DOMAIN,
)
from homeassistant.const import CONF_NAME
from homeassistant.core import HomeAssistant


@pytest.fixture
def mock_setup_entry() -> Generator[MagicMock, None, None]:
    """Create a mock for the nextbus component setup."""
    with patch(
        "homeassistant.components.nextbus.async_setup_entry",
        return_value=True,
    ) as mock_setup_entry:
        yield mock_setup_entry


@pytest.fixture
def mock_nextbus() -> Generator[MagicMock, None, None]:
    """Create a mock py_nextbus module."""
    with patch(
        "homeassistant.components.nextbus.config_flow.NextBusClient"
    ) as NextBusClient:
        yield NextBusClient


@pytest.fixture
def mock_nextbus_lists(mock_nextbus: MagicMock) -> MagicMock:
    """Mock all list functions in nextbus to test validate logic."""
    instance = mock_nextbus.return_value
    instance.get_agency_list.return_value = {
        "agency": [{"tag": "sf-muni", "title": "San Francisco Muni"}]
    }
    instance.get_route_list.return_value = {
        "route": [{"tag": "F", "title": "F - Market & Wharves"}]
    }
    instance.get_route_config.return_value = {
        "route": {"stop": [{"tag": "5650", "title": "Market St & 7th St"}]}
    }

    return instance


async def test_form(
    hass: HomeAssistant, mock_setup_entry: MagicMock, mock_nextbus_lists: MagicMock
) -> None:
    """Test we get the form."""
    await setup.async_setup_component(hass, "persistent_notification", {})
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result.get("type") == "form"
    assert result.get("errors") == {}

    # Select agency
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_AGENCY_NAME: "San Francisco Muni",
        },
    )
    await hass.async_block_till_done()

    assert result.get("type") == "form"
    assert result.get("errors") == {}

    # Select route
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_ROUTE_NAME: "F - Market & Wharves",
        },
    )
    await hass.async_block_till_done()

    assert result.get("type") == "form"
    assert result.get("errors") == {}
    # assert result.get("title") == "Name of the device"

    # Select stop
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_STOP_NAME: "Market St & 7th St",
        },
    )
    await hass.async_block_till_done()

    assert result.get("type") == "form"
    assert result.get("errors") == {}

    # Provide name
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_NAME: "Test Name",
        },
    )
    await hass.async_block_till_done()

    assert result.get("type") == "create_entry"
    assert result.get("data") == {
        "agency": "sf-muni",
        "route": "F",
        "stop": "5650",
        "name": "Test Name",
    }

    assert len(mock_setup_entry.mock_calls) == 1
