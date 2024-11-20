"""Tests for the Zamg config flow."""

from unittest.mock import MagicMock

import pytest
from zamg.exceptions import ZamgApiError

from homeassistant.components.zamg.const import CONF_STATION_ID, DOMAIN, LOGGER
from homeassistant.config_entries import SOURCE_USER
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from .conftest import TEST_STATION_ID


@pytest.mark.usefixtures("mock_zamg", "mock_setup_entry")
async def test_full_user_flow_implementation(hass: HomeAssistant) -> None:
    """Test the full manual user flow from start to finish."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_USER},
    )
    assert result.get("step_id") == "user"
    assert result.get("type") is FlowResultType.FORM
    LOGGER.debug(result)
    assert result.get("data_schema") != ""
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={CONF_STATION_ID: TEST_STATION_ID},
    )
    assert result.get("type") is FlowResultType.CREATE_ENTRY
    assert "data" in result
    assert result["data"][CONF_STATION_ID] == TEST_STATION_ID
    assert "result" in result
    assert result["result"].unique_id == TEST_STATION_ID


@pytest.mark.usefixtures("mock_setup_entry")
async def test_error_closest_station(hass: HomeAssistant, mock_zamg: MagicMock) -> None:
    """Test with error of reading from Zamg."""
    mock_zamg.closest_station.side_effect = ZamgApiError
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_USER},
    )
    assert result.get("type") is FlowResultType.ABORT
    assert result.get("reason") == "cannot_connect"


@pytest.mark.usefixtures("mock_setup_entry")
async def test_error_update(hass: HomeAssistant, mock_zamg: MagicMock) -> None:
    """Test with error of reading from Zamg."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_USER},
    )
    assert result.get("step_id") == "user"
    assert result.get("type") is FlowResultType.FORM
    LOGGER.debug(result)
    assert result.get("data_schema") != ""
    mock_zamg.update.side_effect = ZamgApiError
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={CONF_STATION_ID: TEST_STATION_ID},
    )
    assert result.get("type") is FlowResultType.ABORT
    assert result.get("reason") == "cannot_connect"


@pytest.mark.usefixtures("mock_zamg", "mock_setup_entry")
async def test_user_flow_duplicate(hass: HomeAssistant) -> None:
    """Test the full manual user flow from start to finish."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_USER},
    )

    assert result.get("step_id") == "user"
    assert result.get("type") is FlowResultType.FORM
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={CONF_STATION_ID: TEST_STATION_ID},
    )
    assert result.get("type") is FlowResultType.CREATE_ENTRY
    assert "data" in result
    assert result["data"][CONF_STATION_ID] == TEST_STATION_ID
    assert "result" in result
    assert result["result"].unique_id == TEST_STATION_ID
    # try to add another instance
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_USER},
    )
    assert result.get("step_id") == "user"
    assert result.get("type") is FlowResultType.FORM
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={CONF_STATION_ID: TEST_STATION_ID},
    )
    assert result.get("type") is FlowResultType.ABORT
    assert result.get("reason") == "already_configured"
