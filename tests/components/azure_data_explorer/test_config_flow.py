"""Test the AEH config flow."""
from azure.kusto.data.exceptions import KustoAuthenticationError, KustoServiceError
import pytest

from homeassistant import config_entries, data_entry_flow
from homeassistant.components.azure_data_explorer.const import DOMAIN

from .const import BASE_CONFIG, UPDATE_OPTIONS


async def test_config_flow(hass, mock_setup_entry) -> None:
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
        (Exception(), "unknown"),
    ],
)
async def test_config_flow_errors(
    test_input,
    expected,
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

    mock_execute_query.side_effect = test_input
    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        BASE_CONFIG.copy(),
    )
    assert result2["type"] == data_entry_flow.RESULT_TYPE_FORM
    assert result2["errors"] == {"base": expected}


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
