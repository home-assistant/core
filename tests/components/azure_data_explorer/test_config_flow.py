"""Test the AEH config flow."""
import logging

from azure.kusto.data.exceptions import KustoAuthenticationError
import pytest

from homeassistant import config_entries, data_entry_flow
from homeassistant.components.azure_data_explorer.const import DOMAIN, STEP_USER

from .const import BASE_CONFIG, UPDATE_OPTIONS

_LOGGER = logging.getLogger(__name__)


@pytest.mark.parametrize(
    "step_config, step_id",
    [
        (BASE_CONFIG, STEP_USER),
    ],
    ids=["Base"],
)
async def test_form(
    hass,
    mock_setup_entry,
    step_config,
    step_id,
):
    """Test we get the form."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}, data=None
    )
    assert result["type"] == "form"
    assert result["errors"] is None

    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        step_config.copy(),
    )

    assert result2["type"] == data_entry_flow.RESULT_TYPE_CREATE_ENTRY
    assert result2["title"] == "cluster"
    assert result2["data"] == step_config
    mock_setup_entry.assert_called_once()


@pytest.mark.parametrize(
    "side_effect, error_message",
    [(KustoAuthenticationError, "unknown"), (Exception, "unknown")],
    ids=["invalid_auth", "unknown"],
)
async def test_connection_error(
    hass,
    mock_test_connection,
    side_effect,
    error_message,
):
    """Test we handle connection errors."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_USER},
        data=None,
    )
    assert result["type"] == "form"
    assert result["errors"] is None

    mock_test_connection.side_effect = side_effect
    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        BASE_CONFIG.copy(),
    )
    assert result2["type"] == data_entry_flow.RESULT_TYPE_FORM
    assert result2["errors"] == {"base": error_message}


async def test_options_flow(hass, entry):
    """Test options flow."""
    result = await hass.config_entries.options.async_init(entry.entry_id)

    assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
    assert result["step_id"] == "init"
    assert result["last_step"]

    updated = await hass.config_entries.options.async_configure(
        result["flow_id"], UPDATE_OPTIONS
    )
    assert updated["type"] == data_entry_flow.RESULT_TYPE_CREATE_ENTRY
    assert updated["data"] == UPDATE_OPTIONS
    await hass.async_block_till_done()
