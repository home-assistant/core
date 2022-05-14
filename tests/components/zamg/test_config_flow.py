"""Tests for the Zamg config flow."""
from unittest.mock import MagicMock, patch

from homeassistant.components.zamg.const import CONF_STATION_ID, DOMAIN, LOGGER
from homeassistant.config_entries import SOURCE_IMPORT, SOURCE_USER
from homeassistant.const import CONF_NAME
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import (
    RESULT_TYPE_ABORT,
    RESULT_TYPE_CREATE_ENTRY,
    RESULT_TYPE_FORM,
)

from .conftest import TEST_STATION_ID, TEST_STATION_NAME


async def test_full_user_flow_implementation(
    hass: HomeAssistant,
    mock_zamg: MagicMock,
    mock_setup_entry: None,
) -> None:
    """Test the full manual user flow from start to finish."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_USER},
    )
    assert result.get("step_id") == "user"
    assert result.get("type") == RESULT_TYPE_FORM
    LOGGER.debug(result)
    assert result.get("data_schema") != ""
    assert "flow_id" in result
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={CONF_STATION_ID: int(TEST_STATION_ID)},
    )
    assert result.get("type") == RESULT_TYPE_CREATE_ENTRY
    assert "data" in result
    assert result["data"][CONF_STATION_ID] == TEST_STATION_ID
    assert "result" in result
    assert result["result"].unique_id == TEST_STATION_ID


async def test_error_update(
    hass: HomeAssistant,
    mock_zamg: MagicMock,
    mock_setup_entry: None,
) -> None:
    """Test with error of reading from Zamg."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_USER},
    )
    assert result.get("step_id") == "user"
    assert result.get("type") == RESULT_TYPE_FORM
    LOGGER.debug(result)
    assert result.get("data_schema") != ""
    mock_zamg.update.side_effect = ValueError
    assert "flow_id" in result
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={CONF_STATION_ID: int(TEST_STATION_ID)},
    )
    assert result.get("type") == RESULT_TYPE_ABORT
    assert result.get("reason") == "cannot_connect"


async def test_full_import_flow_implementation(
    hass: HomeAssistant,
    mock_zamg: MagicMock,
    mock_setup_entry: None,
) -> None:
    """Test the full import flow from start to finish."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_IMPORT},
        data={CONF_STATION_ID: TEST_STATION_ID, CONF_NAME: TEST_STATION_NAME},
    )
    assert result.get("type") == RESULT_TYPE_CREATE_ENTRY
    assert result.get("data") == {CONF_STATION_ID: TEST_STATION_ID}


async def test_import_flow_not_found(
    hass: HomeAssistant,
    mock_zamg_stations: MagicMock,
    mock_setup_entry: None,
) -> None:
    """Test the full manual user flow from start to finish."""
    with patch(
        "homeassistant.components.zamg.config_flow.ZamgData",
        side_effect=ValueError(TEST_STATION_ID),
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": SOURCE_IMPORT},
            data={CONF_STATION_ID: TEST_STATION_ID, CONF_NAME: TEST_STATION_NAME},
        )
        assert result.get("type") == RESULT_TYPE_ABORT
        assert result.get("reason") == "unknown"


async def test_user_flow_duplicate(
    hass: HomeAssistant,
    mock_zamg: MagicMock,
    mock_setup_entry: None,
) -> None:
    """Test the full manual user flow from start to finish."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_USER},
    )

    assert result.get("step_id") == "user"
    assert result.get("type") == RESULT_TYPE_FORM
    assert "flow_id" in result
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={CONF_STATION_ID: int(TEST_STATION_ID)},
    )
    assert result.get("type") == RESULT_TYPE_CREATE_ENTRY
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
    assert result.get("type") == RESULT_TYPE_FORM
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={CONF_STATION_ID: int(TEST_STATION_ID)},
    )
    assert result.get("type") == RESULT_TYPE_ABORT
    assert result.get("reason") == "already_configured"
