"""Test the AEH config flow."""
import logging

from azure.kusto.data.exceptions import KustoAuthenticationError, KustoServiceError
import pytest

from homeassistant import config_entries, data_entry_flow
from homeassistant.components.azure_data_explorer.const import DOMAIN, STEP_USER

from .const import BASE_CONFIG, BASE_CONFIG_FULL, UPDATE_OPTIONS

from tests.common import MockConfigEntry

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
    mock_setup_entry.assert_called_once()


async def test_connection_error_KustoServiceError(
    hass,
    mock_execute_query,
):
    """Test we handle connection KustoServiceError."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_USER},
        data=None,
    )
    assert result["type"] == "form"
    assert result["errors"] is None

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
):
    """Test we handle connection KustoAuthenticationError."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_USER},
        data=None,
    )
    assert result["type"] == "form"
    assert result["errors"] is None

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
):
    """Test we handle connection KustoAuthenticationError."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_USER},
        data=None,
    )
    assert result["type"] == "form"
    assert result["errors"] is None

    mock_execute_query.side_effect = Exception
    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        BASE_CONFIG.copy(),
    )
    assert result2["type"] == data_entry_flow.RESULT_TYPE_FORM
    assert result2["errors"] == {"base": "unknown"}


async def test_single_instance(hass):
    """Test uniqueness of username."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data=BASE_CONFIG_FULL,
        title="test-instance",
    )
    entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_USER},
        data=BASE_CONFIG_FULL,
    )
    assert result["type"] == data_entry_flow.RESULT_TYPE_ABORT
    assert result["reason"] == "single_instance_allowed"


async def test_options_flow(hass, entry_managed):
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
