"""Test the AEH config flow."""
import logging
from unittest.mock import patch

from azure.eventhub.exceptions import EventHubError
import pytest

from homeassistant import config_entries, data_entry_flow
from homeassistant.components.azure_event_hub.client import ClientCreationError
from homeassistant.components.azure_event_hub.const import (
    CONF_MAX_DELAY,
    CONF_SEND_INTERVAL,
    DOMAIN,
    STEP_CONN_STRING,
    STEP_SAS,
)

from .const import (
    BASE_CONFIG_CS,
    BASE_CONFIG_SAS,
    BASIC_OPTIONS,
    CONFIG_FLOW_PATH,
    CS_CONFIG,
    CS_CONFIG_FULL,
    IMPORT_CONFIG,
    SAS_CONFIG,
    SAS_CONFIG_FULL,
    UPDATE_OPTIONS,
)

from tests.common import MockConfigEntry

_LOGGER = logging.getLogger(__name__)


@pytest.mark.parametrize(
    "step1_config, step_id, step2_config, data_config",
    [
        (BASE_CONFIG_CS, STEP_CONN_STRING, CS_CONFIG, CS_CONFIG_FULL),
        (BASE_CONFIG_SAS, STEP_SAS, SAS_CONFIG, SAS_CONFIG_FULL),
    ],
)
async def test_form(
    hass,
    mock_setup_entry,
    mock_aeh,
    step1_config,
    step_id,
    step2_config,
    data_config,
):
    """Test we get the form."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}, data=None
    )
    assert result["type"] == "form"
    assert result["errors"] is None
    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        step1_config.copy(),
    )
    await hass.async_block_till_done()

    assert result2["type"] == "form"
    assert result2["step_id"] == step_id
    result3 = await hass.config_entries.flow.async_configure(
        result2["flow_id"],
        step2_config.copy(),
    )
    await hass.async_block_till_done()
    assert result3["type"] == data_entry_flow.RESULT_TYPE_CREATE_ENTRY
    assert result3["title"] == "test-instance"
    assert result3["data"] == data_config
    assert len(mock_setup_entry.mock_calls) == 1


async def test_import(hass, mock_setup_entry):
    """Test we get the form."""

    import_config = IMPORT_CONFIG.copy()
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_IMPORT},
        data=IMPORT_CONFIG.copy(),
    )

    await hass.async_block_till_done()

    assert result["type"] == data_entry_flow.RESULT_TYPE_CREATE_ENTRY
    assert result["title"] == "test-instance"
    options = {
        CONF_SEND_INTERVAL: import_config.pop(CONF_SEND_INTERVAL),
        CONF_MAX_DELAY: import_config.pop(CONF_MAX_DELAY),
    }
    assert result["data"] == import_config
    assert result["options"] == options
    assert len(mock_setup_entry.mock_calls) == 1


@pytest.mark.parametrize(
    "source", [config_entries.SOURCE_USER, config_entries.SOURCE_IMPORT]
)
async def test_single_instance(hass, source):
    """Test uniqueness of username."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data=CS_CONFIG_FULL,
        title="test-instance",
    )
    entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": source},
        data=BASE_CONFIG_CS.copy(),
    )
    await hass.async_block_till_done()

    assert result["type"] == data_entry_flow.RESULT_TYPE_ABORT
    assert result["reason"] == "single_instance_allowed"


@pytest.mark.parametrize(
    "step1_config, step2_config, side_effect, error_message",
    [
        (BASE_CONFIG_CS, CS_CONFIG, ClientCreationError, "invalid_conn_string"),
        (BASE_CONFIG_SAS, SAS_CONFIG, ClientCreationError, "invalid_sas"),
        (BASE_CONFIG_CS, CS_CONFIG, Exception, "unknown"),
        (BASE_CONFIG_SAS, SAS_CONFIG, Exception, "unknown"),
    ],
)
async def test_client_creation_error(
    hass,
    mock_aeh,
    step1_config,
    step2_config,
    side_effect,
    error_message,
):
    """Test we handle client creation errors."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}, data=step1_config.copy()
    )
    assert result["type"] == "form"
    assert result["errors"] is None
    with patch(
        f"{CONFIG_FLOW_PATH}.AzureEventHubClient.from_input", side_effect=side_effect
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            step2_config.copy(),
        )
        assert result2["type"] == data_entry_flow.RESULT_TYPE_FORM
        assert result2["errors"] == {"base": error_message}


@pytest.mark.parametrize(
    "side_effect, error_message",
    [(EventHubError("test"), "cannot_connect"), (Exception, "unknown")],
)
@pytest.mark.parametrize(
    "step1_config, step2_config",
    [(BASE_CONFIG_CS, CS_CONFIG), (BASE_CONFIG_SAS, SAS_CONFIG)],
)
async def test_connection_error(
    hass, mock_aeh, step1_config, step2_config, side_effect, error_message
):
    """Test we handle connection errors."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}, data=step1_config.copy()
    )
    assert result["type"] == "form"
    assert result["errors"] is None
    mock_aeh.test_connection.side_effect = side_effect
    with patch(
        f"{CONFIG_FLOW_PATH}.AzureEventHubClient.from_input",
        return_value=mock_aeh,
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            step2_config.copy(),
        )
        assert result2["type"] == data_entry_flow.RESULT_TYPE_FORM
        assert result2["errors"] == {"base": error_message}


async def test_options(hass, mock_setup_entry):
    """Test options flow."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data=CS_CONFIG_FULL,
        title="test-instance",
        options=BASIC_OPTIONS,
    )
    entry.add_to_hass(hass)

    result = await hass.config_entries.options.async_init(entry.entry_id)

    assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
    assert result["step_id"] == "options"
    assert result["last_step"]

    updated = await hass.config_entries.options.async_configure(
        result["flow_id"], UPDATE_OPTIONS
    )
    assert updated["type"] == data_entry_flow.RESULT_TYPE_CREATE_ENTRY
    assert updated["data"] == UPDATE_OPTIONS
