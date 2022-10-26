"""Tests for the Zamg config flow."""
from unittest.mock import MagicMock

from homeassistant.components.zamg.const import CONF_STATION_ID, DOMAIN, LOGGER
from homeassistant.config_entries import SOURCE_IMPORT, SOURCE_USER
from homeassistant.const import CONF_NAME
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

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
    assert result.get("type") == FlowResultType.FORM
    LOGGER.debug(result)
    assert result.get("data_schema") != ""
    assert "flow_id" in result
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={CONF_STATION_ID: int(TEST_STATION_ID)},
    )
    assert result.get("type") == FlowResultType.CREATE_ENTRY
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
    assert result.get("type") == FlowResultType.FORM
    LOGGER.debug(result)
    assert result.get("data_schema") != ""
    mock_zamg.update.side_effect = ValueError
    assert "flow_id" in result
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={CONF_STATION_ID: int(TEST_STATION_ID)},
    )
    assert result.get("type") == FlowResultType.ABORT
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
    assert result.get("type") == FlowResultType.CREATE_ENTRY
    assert result.get("data") == {CONF_STATION_ID: TEST_STATION_ID}


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
    assert result.get("type") == FlowResultType.FORM
    assert "flow_id" in result
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={CONF_STATION_ID: int(TEST_STATION_ID)},
    )
    assert result.get("type") == FlowResultType.CREATE_ENTRY
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
    assert result.get("type") == FlowResultType.FORM
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={CONF_STATION_ID: int(TEST_STATION_ID)},
    )
    assert result.get("type") == FlowResultType.ABORT
    assert result.get("reason") == "already_configured"


async def test_import_flow_duplicate(
    hass: HomeAssistant,
    mock_zamg: MagicMock,
    mock_setup_entry: None,
) -> None:
    """Test import flow with duplicate entry."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_USER},
    )

    assert result.get("step_id") == "user"
    assert result.get("type") == FlowResultType.FORM
    assert "flow_id" in result
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={CONF_STATION_ID: int(TEST_STATION_ID)},
    )
    assert result.get("type") == FlowResultType.CREATE_ENTRY
    assert "data" in result
    assert result["data"][CONF_STATION_ID] == TEST_STATION_ID
    assert "result" in result
    assert result["result"].unique_id == TEST_STATION_ID
    # try to add another instance
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_IMPORT},
        data={CONF_STATION_ID: TEST_STATION_ID, CONF_NAME: TEST_STATION_NAME},
    )
    assert result.get("type") == FlowResultType.ABORT
    assert result.get("reason") == "already_configured"


async def test_import_flow_duplicate_after_position(
    hass: HomeAssistant,
    mock_zamg: MagicMock,
    mock_setup_entry: None,
) -> None:
    """Test import flow with duplicate entry."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_USER},
    )

    assert result.get("step_id") == "user"
    assert result.get("type") == FlowResultType.FORM
    assert "flow_id" in result
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={CONF_STATION_ID: int(TEST_STATION_ID)},
    )
    assert result.get("type") == FlowResultType.CREATE_ENTRY
    assert "data" in result
    assert result["data"][CONF_STATION_ID] == TEST_STATION_ID
    assert "result" in result
    assert result["result"].unique_id == TEST_STATION_ID
    # try to add another instance
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_IMPORT},
        data={CONF_STATION_ID: "123", CONF_NAME: TEST_STATION_NAME},
    )
    assert result.get("type") == FlowResultType.ABORT
    assert result.get("reason") == "already_configured"


async def test_import_flow_no_name(
    hass: HomeAssistant,
    mock_zamg: MagicMock,
    mock_setup_entry: None,
) -> None:
    """Test the full import flow from start to finish."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_IMPORT},
        data={CONF_STATION_ID: TEST_STATION_ID},
    )
    assert result.get("type") == FlowResultType.CREATE_ENTRY
    assert result.get("data") == {CONF_STATION_ID: TEST_STATION_ID}
