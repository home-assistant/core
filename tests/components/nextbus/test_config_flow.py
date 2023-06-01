"""Test the NextBus config flow."""
from collections.abc import Generator
from unittest.mock import MagicMock, patch

import pytest

from homeassistant import config_entries, setup
from homeassistant.components.nextbus.const import (
    CONF_AGENCY,
    CONF_ROUTE,
    CONF_STOP,
    DOMAIN,
)
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
    assert result.get("title") == "sf-muni F"
    assert result.get("data") == {
        "agency": "sf-muni",
        "route": "F",
        "stop": "5650",
    }

    assert len(mock_setup_entry.mock_calls) == 1

    # Check duplicate entries are aborted
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

    assert result.get("type") == "abort"
    assert result.get("reason") == "already_configured"


@pytest.mark.parametrize(
    ("override", "expected_reason"),
    (
        ({CONF_AGENCY: "not muni"}, "invalid_agency"),
        ({CONF_ROUTE: "not F"}, "invalid_route"),
        ({CONF_STOP: "not 5650"}, "invalid_stop"),
    ),
)
async def test_import_config_invalid(
    hass: HomeAssistant,
    mock_setup_entry: MagicMock,
    mock_nextbus_lists: MagicMock,
    override: dict[str, str],
    expected_reason: str,
) -> None:
    """Test user is redirected to user setup flow because they have invalid config."""
    await setup.async_setup_component(hass, "persistent_notification", {})

    data = {
        CONF_AGENCY: "sf-muni",
        CONF_ROUTE: "F",
        CONF_STOP: "5650",
    }
    data.update(override)

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_IMPORT},
        data=data,
    )
    await hass.async_block_till_done()

    assert result.get("type") == "abort"
    assert result.get("reason") == expected_reason


async def test_user_config(
    hass: HomeAssistant, mock_setup_entry: MagicMock, mock_nextbus_lists: MagicMock
) -> None:
    """Test we get the form."""
    await setup.async_setup_component(hass, "persistent_notification", {})
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result.get("type") == "form"
    assert result.get("step_id") == "agency"

    # Select agency
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_AGENCY: "sf-muni",
        },
    )
    await hass.async_block_till_done()

    assert result.get("type") == "form"
    assert result.get("step_id") == "route"

    # Select route
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_ROUTE: "F",
        },
    )
    await hass.async_block_till_done()

    assert result.get("type") == "form"
    assert result.get("step_id") == "stop"

    # Select stop
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_STOP: "5650",
        },
    )
    await hass.async_block_till_done()

    assert result.get("type") == "create_entry"
    assert result.get("data") == {
        "agency": "sf-muni",
        "route": "F",
        "stop": "5650",
    }

    assert len(mock_setup_entry.mock_calls) == 1
