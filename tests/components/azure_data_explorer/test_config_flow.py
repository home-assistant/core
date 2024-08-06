"""Test the Azure Data Explorer config flow."""

from unittest.mock import AsyncMock, MagicMock

from azure.kusto.data.exceptions import KustoAuthenticationError, KustoServiceError
import pytest

from homeassistant import config_entries, data_entry_flow
from homeassistant.components.azure_data_explorer.const import DOMAIN
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

    assert result2["type"] == data_entry_flow.RESULT_TYPE_CREATE_ENTRY
    assert result2["title"] == "cluster.region.kusto.windows.net"
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
    assert result2["type"] == data_entry_flow.RESULT_TYPE_FORM
    assert result2["errors"] == {"base": expected}

    await hass.async_block_till_done()

    assert result2["type"] == data_entry_flow.RESULT_TYPE_FORM

    # Retest error handling if error is corrected and connection is successful

    mock_execute_query.side_effect = None

    result3 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        BASE_CONFIG.copy(),
    )

    await hass.async_block_till_done()

    assert result3["type"] == data_entry_flow.RESULT_TYPE_CREATE_ENTRY
