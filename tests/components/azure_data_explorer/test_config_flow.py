"""Test the Azure Data Explorer config flow."""

from unittest.mock import AsyncMock, MagicMock

from azure.kusto.data.exceptions import KustoAuthenticationError, KustoServiceError
import probatio
import pytest
from pytest_homeassistant.common import MockConfigEntry

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

from .const import BASE_CONFIG, BASE_CONFIG_FULL, BASIC_OPTIONS

REAUTH_INPUT = {
    CONF_APP_REG_ID: "new-app-reg-id",
    CONF_APP_REG_SECRET: "new-app-reg-secret",
    CONF_AUTHORITY_ID: "new-auth-id",
}


async def test_config_flow(hass: HomeAssistant, mock_setup_entry: AsyncMock) -> None:
    """Test we get the form."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    assert result["type"] is data_entry_flow.FlowResultType.FORM
    assert result["step_id"] == "user"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input=None,
    )
    assert result["type"] is data_entry_flow.FlowResultType.FORM
    assert result["errors"] == {}

    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        BASE_CONFIG.copy(),
    )

    assert result2["type"] is data_entry_flow.FlowResultType.CREATE_ENTRY
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
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    assert result["type"] is data_entry_flow.FlowResultType.FORM
    assert result["step_id"] == "user"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input=None,
    )
    assert result["type"] is data_entry_flow.FlowResultType.FORM
    assert result["errors"] == {}

    # Test error handling with error

    mock_execute_query.side_effect = test_input
    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        BASE_CONFIG.copy(),
    )
    assert result2["type"] is data_entry_flow.FlowResultType.FORM
    assert result2["errors"] == {"base": expected}

    schema = result2["data_schema"]
    assert isinstance(schema, probatio.Schema)

    suggested_values = {
        key.schema: key.description.get("suggested_value")
        for key in schema.schema
        if isinstance(key, probatio.Marker)
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

    assert result2["type"] is data_entry_flow.FlowResultType.FORM

    # Retest error handling if error is corrected and connection is successful

    mock_execute_query.side_effect = None

    result3 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        BASE_CONFIG.copy(),
    )

    await hass.async_block_till_done()

    assert result3["type"] is data_entry_flow.FlowResultType.CREATE_ENTRY


def _suggested_values(schema: probatio.Schema) -> dict[str, str | None]:
    return {
        key.schema: key.description.get("suggested_value")
        for key in schema.schema
        if isinstance(key, probatio.Marker) and key.description
    }


async def test_reauth(hass: HomeAssistant, mock_setup_entry: AsyncMock) -> None:
    """Test reauthentication updates the credentials and reloads the entry."""
    entry = MockConfigEntry(domain=DOMAIN, data=BASE_CONFIG_FULL, options=BASIC_OPTIONS)
    entry.add_to_hass(hass)

    result = await entry.start_reauth_flow(hass)
    assert result["type"] is data_entry_flow.FlowResultType.FORM
    assert result["step_id"] == "reauth_confirm"
    assert _suggested_values(result["data_schema"]) == {
        CONF_APP_REG_ID: BASE_CONFIG_FULL[CONF_APP_REG_ID],
        CONF_AUTHORITY_ID: BASE_CONFIG_FULL[CONF_AUTHORITY_ID],
    }

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], REAUTH_INPUT
    )
    await hass.async_block_till_done()

    assert result["type"] is data_entry_flow.FlowResultType.ABORT
    assert result["reason"] == "reauth_successful"
    assert entry.data == BASE_CONFIG_FULL | REAUTH_INPUT
    mock_setup_entry.assert_called_once()


@pytest.mark.parametrize(
    ("side_effect", "error"),
    [
        pytest.param(KustoServiceError("test"), "cannot_connect", id="cannot_connect"),
        pytest.param(
            KustoAuthenticationError("test", Exception),
            "invalid_auth",
            id="invalid_auth",
        ),
    ],
)
async def test_reauth_errors(
    hass: HomeAssistant,
    mock_setup_entry: AsyncMock,
    mock_execute_query: MagicMock,
    side_effect: Exception,
    error: str,
) -> None:
    """Test reauthentication errors and recovery."""
    entry = MockConfigEntry(domain=DOMAIN, data=BASE_CONFIG_FULL, options=BASIC_OPTIONS)
    entry.add_to_hass(hass)

    result = await entry.start_reauth_flow(hass)

    mock_execute_query.side_effect = side_effect
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], REAUTH_INPUT
    )
    assert result["type"] is data_entry_flow.FlowResultType.FORM
    assert result["errors"] == {"base": error}
    assert _suggested_values(result["data_schema"]) == {
        CONF_APP_REG_ID: REAUTH_INPUT[CONF_APP_REG_ID],
        CONF_AUTHORITY_ID: REAUTH_INPUT[CONF_AUTHORITY_ID],
    }

    mock_execute_query.side_effect = None
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], REAUTH_INPUT
    )
    await hass.async_block_till_done()

    assert result["type"] is data_entry_flow.FlowResultType.ABORT
    assert result["reason"] == "reauth_successful"
    assert entry.data == BASE_CONFIG_FULL | REAUTH_INPUT
    mock_setup_entry.assert_called_once()
