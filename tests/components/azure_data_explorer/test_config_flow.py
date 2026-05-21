"""Test the Azure Data Explorer config flow."""

from unittest.mock import AsyncMock, MagicMock

from azure.kusto.data.exceptions import KustoAuthenticationError, KustoServiceError
import pytest
import voluptuous as vol

from homeassistant import config_entries, data_entry_flow
from homeassistant.components.azure_data_explorer.const import (
    CONF_ADX_CLUSTER_INGEST_URI,
    CONF_ADX_DATABASE_NAME,
    CONF_ADX_TABLE_NAME,
    CONF_APP_REG_ID,
    CONF_APP_REG_SECRET,
    CONF_AUTHORITY_ID,
    DOMAIN,
)
from homeassistant.core import HomeAssistant

from .const import BASE_CONFIG


async def test_config_flow(hass: HomeAssistant, mock_setup_entry: AsyncMock) -> None:
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

    assert result2["type"] == data_entry_flow.FlowResultType.CREATE_ENTRY
    assert (
        result2["title"]
        == "cluster.region.kusto.windows.net / test-database-name (test-table-name)"
    )
    mock_setup_entry.assert_called_once()


@pytest.mark.parametrize(
    ("test_input", "expected"),
    [
        (KustoServiceError("test"), "cannot_connect"),
        (KustoAuthenticationError("test", Exception), "invalid_auth"),
    ],
)
async def test_config_flow_errors(
    test_input: Exception,
    expected: str,
    hass: HomeAssistant,
    mock_execute_query: MagicMock,
) -> None:
    """Test we handle connection KustoServiceError."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_USER},
        data=None,
    )
    assert result["type"] == data_entry_flow.FlowResultType.FORM
    assert result["errors"] == {}

    # Test error handling with error

    mock_execute_query.side_effect = test_input
    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        BASE_CONFIG.copy(),
    )
    assert result2["type"] == data_entry_flow.FlowResultType.FORM
    assert result2["errors"] == {"base": expected}

    schema = result2["data_schema"]
    assert isinstance(schema, vol.Schema)

    suggested_values = {
        key.schema: key.description.get("suggested_value")
        for key in schema.schema
        if isinstance(key, vol.Marker)
        and key.description
        and "suggested_value" in key.description
    }

    assert (
        suggested_values[CONF_ADX_CLUSTER_INGEST_URI]
        == BASE_CONFIG[CONF_ADX_CLUSTER_INGEST_URI]
    )
    assert (
        suggested_values[CONF_ADX_DATABASE_NAME] == BASE_CONFIG[CONF_ADX_DATABASE_NAME]
    )
    assert suggested_values[CONF_ADX_TABLE_NAME] == BASE_CONFIG[CONF_ADX_TABLE_NAME]
    assert suggested_values[CONF_APP_REG_ID] == BASE_CONFIG[CONF_APP_REG_ID]
    assert suggested_values[CONF_APP_REG_SECRET] == BASE_CONFIG[CONF_APP_REG_SECRET]
    assert suggested_values[CONF_AUTHORITY_ID] == BASE_CONFIG[CONF_AUTHORITY_ID]

    await hass.async_block_till_done()

    assert result2["type"] == data_entry_flow.FlowResultType.FORM

    # Retest error handling if error is corrected and connection is successful

    mock_execute_query.side_effect = None

    result3 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        BASE_CONFIG.copy(),
    )

    await hass.async_block_till_done()

    assert result3["type"] == data_entry_flow.FlowResultType.CREATE_ENTRY
