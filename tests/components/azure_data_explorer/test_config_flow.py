"""Test the AEH config flow."""

from azure.kusto.data.exceptions import KustoAuthenticationError, KustoServiceError

from homeassistant import config_entries, data_entry_flow
from homeassistant.components.azure_data_explorer.const import DOMAIN

from .const import BASE_CONFIG, UPDATE_OPTIONS


async def test_form(hass, mock_setup_entry) -> None:
    """Test we get the form."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}, data=None
    )
    assert result["type"] == data_entry_flow.FlowResultType.FORM
    assert result["errors"] == {}

    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        BASE_CONFIG.copy(),
    )

    assert result2["type"] == data_entry_flow.RESULT_TYPE_CREATE_ENTRY
    assert result2["title"] == "cluster"
    mock_setup_entry.assert_called_once()


async def test_connection_error_KustoServiceError(
    hass,
    mock_execute_query,
) -> None:
    """Test we handle connection KustoServiceError."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_USER},
        data=None,
    )
    assert result["type"] == data_entry_flow.FlowResultType.FORM
    assert result["errors"] == {}

    mock_execute_query.side_effect = KustoServiceError("test")
    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        BASE_CONFIG.copy(),
    )
    assert result2["type"] == data_entry_flow.RESULT_TYPE_FORM
    assert result2["errors"] == {"base": "cannot_connect"}


async def test_connection_error_KustoAuthenticationError(
    hass,
    mock_execute_query,
) -> None:
    """Test we handle connection KustoAuthenticationError."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_USER},
        data=None,
    )
    assert result["type"] == data_entry_flow.FlowResultType.FORM
    assert result["errors"] == {}

    mock_execute_query.side_effect = KustoAuthenticationError("test", Exception)
    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        BASE_CONFIG.copy(),
    )
    assert result2["type"] == data_entry_flow.RESULT_TYPE_FORM
    assert result2["errors"] == {"base": "invalid_auth"}


async def test_connection_error_Exception(
    hass,
    mock_execute_query,
) -> None:
    """Test we handle connection KustoAuthenticationError."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_USER},
        data=None,
    )
    assert result["type"] == data_entry_flow.FlowResultType.FORM
    assert result["errors"] == {}

    mock_execute_query.side_effect = Exception
    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        BASE_CONFIG.copy(),
    )
    assert result2["type"] == data_entry_flow.RESULT_TYPE_FORM
    assert result2["errors"] == {"base": "unknown"}


async def test_options_flow(hass, entry_managed) -> None:
    """Test options flow."""
    result = await hass.config_entries.options.async_init(entry_managed.entry_id)

    assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
    assert result["step_id"] == "init"
    assert result["last_step"]

    updated = await hass.config_entries.options.async_configure(
        result["flow_id"], UPDATE_OPTIONS
    )
    assert updated["type"] == data_entry_flow.RESULT_TYPE_CREATE_ENTRY
    assert updated["data"] == UPDATE_OPTIONS
    await hass.async_block_till_done()
