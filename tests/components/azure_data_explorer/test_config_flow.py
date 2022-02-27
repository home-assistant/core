"""Test the AEH config flow."""
import logging

from azure.kusto.data.exceptions import KustoAuthenticationError, KustoServiceError
from numpy import equal
import pytest

from homeassistant import config_entries, data_entry_flow
from homeassistant.components.azure_data_explorer.config_flow import ConfigFlow
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


@pytest.mark.parametrize(
    "side_effect, error_message",
    [("base", "invalid_auth"), ("base", "cannot_connect"), ("base", "unknown")],
    ids=["invalid_auth", "cannot_connect", "unknown"],
)
async def test_connection_error(
    hass,
    mock_validate_input,
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

    mock_validate_input.side_effect = {side_effect: error_message}
    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        BASE_CONFIG.copy(),
    )
    assert result2["type"] == data_entry_flow.RESULT_TYPE_FORM
    assert result2["errors"] == side_effect


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


@pytest.mark.parametrize(
    "source",
    [config_entries.SOURCE_USER],
    ids=["user"],
)
async def test_single_instance(hass, source):
    """Test uniqueness of username."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data=BASE_CONFIG_FULL,
        title="test-instance",
    )
    entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": source},
        data=BASE_CONFIG.copy(),
    )
    assert result["type"] == data_entry_flow.RESULT_TYPE_ABORT
    assert result["reason"] == "single_instance_allowed"


async def test_validate_input(
    hass,
    mock_test_connection,
):
    """Test we get the form."""
    config_flow = ConfigFlow()

    result = await config_flow.validate_input(hass, BASE_CONFIG_FULL)

    assert result is None

    mock_test_connection.side_effect = KustoServiceError("msg")
    result = await config_flow.validate_input(hass, BASE_CONFIG_FULL)

    assert equal(result, {"base": "cannot_connect"})

    mock_test_connection.side_effect = KustoAuthenticationError(
        authentication_method="AM", exception=Exception
    )
    result = await config_flow.validate_input(hass, BASE_CONFIG_FULL)

    assert equal(result, {"base": "invalid_auth"})

    mock_test_connection.side_effect = Exception
    result = await config_flow.validate_input(hass, BASE_CONFIG_FULL)

    assert equal(result, {"base": "unknown"})
