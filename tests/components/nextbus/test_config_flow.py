"""Test the NextBus config flow."""

from collections.abc import Generator
from unittest.mock import MagicMock, patch

import pytest

from homeassistant import config_entries, setup
from homeassistant.components.nextbus.config_flow import NextBusFlowHandler
from homeassistant.components.nextbus.const import (
    CONF_AGENCY,
    CONF_AGENCY_NAME,
    CONF_ROUTE,
    CONF_ROUTE_NAME,
    CONF_STOP,
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


async def test_import_config(
    hass: HomeAssistant, mock_setup_entry: MagicMock, mock_nextbus_lists: MagicMock
) -> None:
    """Test config is imported and component set up."""
    await setup.async_setup_component(hass, "persistent_notification", {})
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_IMPORT},
        data={
            CONF_AGENCY: "sf-muni",
            CONF_ROUTE: "F",
            CONF_STOP: "5650",
        },
    )
    await hass.async_block_till_done()

    assert result.get("type") == "create_entry"
    assert result.get("data") == {
        "agency": "sf-muni",
        "route": "F",
        "stop": "5650",
        "name": "sf-muni F",
    }

    assert len(mock_setup_entry.mock_calls) == 1


async def test_import_config_invalid(
    hass: HomeAssistant, mock_setup_entry: MagicMock, mock_nextbus_lists: MagicMock
) -> None:
    """Test user is redirected to user setup flow because they have invalid config."""
    await setup.async_setup_component(hass, "persistent_notification", {})
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_IMPORT},
        data={
            CONF_AGENCY: "not muni",
            CONF_ROUTE: "F",
            CONF_STOP: "5650",
        },
    )
    await hass.async_block_till_done()

    assert result.get("type") == "form"
    assert result.get("step_id") == "agency"


async def test_import_config_nothing_to_import(
    hass: HomeAssistant, mock_setup_entry: MagicMock, mock_nextbus_lists: MagicMock
) -> None:
    """Test import is aborted missing config."""
    await setup.async_setup_component(hass, "persistent_notification", {})
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_IMPORT},
        data={},
    )
    await hass.async_block_till_done()

    assert result.get("type") == "abort"


async def test_invalid_user_config(
    hass: HomeAssistant, mock_nextbus_lists: MagicMock
) -> None:
    """Test invalid config in config flow.

    These scenarios shouldn't really happen if a user steps through the flow.
    If they managed to skip around, they should be sent backwards. This tests
    that behaviour.
    """
    flow_handler = NextBusFlowHandler()
    flow_handler.hass = hass

    # Name flow step back missing agency
    result = await flow_handler.async_step_name()
    assert result.get("step_id") == "agency"

    # Stop flow step back missing agency
    result = await flow_handler.async_step_stop()
    assert result.get("step_id") == "agency"

    # Route flow step back missing agency
    result = await flow_handler.async_step_route()
    assert result.get("step_id") == "agency"

    # Name flow step back missing route
    flow_handler.nextbus_config[CONF_AGENCY] = "sf-muni"
    result = await flow_handler.async_step_name()
    assert result.get("step_id") == "route"

    # Stop flow step back missing route
    result = await flow_handler.async_step_stop()
    assert result.get("step_id") == "route"


async def test_user_config(
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
