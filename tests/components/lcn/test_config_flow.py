"""Tests for the LCN config flow."""
from unittest.mock import patch

import pypck
from pypck.connection import PchkAuthenticationError, PchkLicenseError
import pytest

from homeassistant import config_entries, data_entry_flow
from homeassistant.components.lcn.config_flow import validate_connection
from homeassistant.components.lcn.const import CONF_DIM_MODE, CONF_SK_NUM_TRIES, DOMAIN
from homeassistant.const import CONF_BASE, CONF_HOST

from .conftest import CONNECTION_DATA, DATA, OPTIONS, MockPchkConnectionManager

from tests.common import MockConfigEntry


@patch.object(pypck.connection, "PchkConnectionManager", MockPchkConnectionManager)
async def test_step_import(hass):
    """Test for import step."""
    config_data = CONNECTION_DATA.copy()
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_IMPORT}, data=config_data
    )
    await hass.async_block_till_done()

    assert result["type"] == data_entry_flow.RESULT_TYPE_CREATE_ENTRY
    assert result["title"] == CONNECTION_DATA[CONF_HOST]
    assert result["data"] == CONNECTION_DATA


async def test_step_import_existing_host(hass):
    """Test for update of config_entry if imported host already exists."""
    # Create config entry and add it to hass
    mock_options = OPTIONS.copy()
    mock_options.update({CONF_SK_NUM_TRIES: 3, CONF_DIM_MODE: "STEPS50"})
    mock_entry = MockConfigEntry(
        version=2, title="pchk", domain=DOMAIN, data=DATA, options=mock_options
    )
    mock_entry.add_to_hass(hass)
    # Inititalize a config flow with different data but same host name
    imported_data = CONNECTION_DATA.copy()
    with patch("pypck.connection.PchkConnectionManager.async_connect"):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_IMPORT}, data=imported_data
        )
    await hass.async_block_till_done()

    # Check if first config entry was not updated
    assert result["type"] == data_entry_flow.RESULT_TYPE_ABORT
    assert result["reason"] == "existing_configuration_updated"
    assert mock_entry.source == config_entries.SOURCE_IMPORT
    assert mock_entry.data == CONNECTION_DATA


async def test_step_import_non_existing_entry(hass):
    """Test for update of config_entry if imported host already exists."""
    # Inititalize a config flow with missing connection parameters and no corresponding entry
    imported_data = {CONF_HOST: "pchk"} | DATA.copy()
    with patch("pypck.connection.PchkConnectionManager.async_connect"):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_IMPORT}, data=imported_data
        )
    await hass.async_block_till_done()

    # Check if first config entry was not updated
    assert result["type"] == data_entry_flow.RESULT_TYPE_ABORT
    assert result["reason"] == "import_connection_error"


@pytest.mark.parametrize(
    "error,reason",
    [
        (PchkAuthenticationError, "authentication_error"),
        (PchkLicenseError, "license_error"),
        (TimeoutError, "connection_refused"),
        (ConnectionRefusedError, "connection_refused"),
    ],
)
async def test_step_import_error(hass, error, reason):
    """Test for error in import is handled correctly."""
    with patch(
        "pypck.connection.PchkConnectionManager.async_connect", side_effect=error
    ):
        config_data = CONNECTION_DATA.copy()
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_IMPORT}, data=config_data
        )
        await hass.async_block_till_done()

        assert result["type"] == data_entry_flow.FlowResultType.ABORT
        assert result["reason"] == reason


@patch.object(pypck.connection, "PchkConnectionManager", MockPchkConnectionManager)
async def test_step_user(hass):
    """Test for user step."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    await hass.async_block_till_done()

    assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
    assert result["step_id"] == "user"

    config_data = CONNECTION_DATA.copy()
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}, data=config_data
    )
    await hass.async_block_till_done()

    assert result["type"] == data_entry_flow.RESULT_TYPE_CREATE_ENTRY
    assert result["title"] == CONNECTION_DATA[CONF_HOST]
    assert result["data"] == DATA
    assert result["options"] == OPTIONS


async def test_step_user_existing_host(hass, entry):
    """Test for user defined host already exists."""
    entry.add_to_hass(hass)

    config_data = CONNECTION_DATA.copy()
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}, data=config_data
    )
    await hass.async_block_till_done()

    assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
    assert result["errors"] == {CONF_HOST: "already_configured"}


@pytest.mark.parametrize(
    "error,reason",
    [
        (PchkAuthenticationError, "authentication_error"),
        (PchkLicenseError, "license_error"),
        (TimeoutError, "connection_refused"),
        (ConnectionRefusedError, "connection_refused"),
    ],
)
async def test_step_user_error(hass, error, reason):
    """Test for error in user step is handled correctly."""
    with patch(
        "pypck.connection.PchkConnectionManager.async_connect", side_effect=error
    ):
        config_data = CONNECTION_DATA.copy()
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}, data=config_data
        )
        await hass.async_block_till_done()

    assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
    assert result["errors"] == {CONF_BASE: reason}


@patch.object(pypck.connection, "PchkConnectionManager", MockPchkConnectionManager)
async def test_options_flow(hass, entry):
    """Test config flow options."""
    entry.add_to_hass(hass)

    result = await hass.config_entries.options.async_init(entry.entry_id)
    await hass.async_block_till_done()

    assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
    assert result["step_id"] == "host_options"

    result = await hass.config_entries.options.async_configure(
        result["flow_id"], user_input=OPTIONS.copy()
    )
    await hass.async_block_till_done()

    assert result["type"] == data_entry_flow.RESULT_TYPE_CREATE_ENTRY
    assert entry.options == OPTIONS


@pytest.mark.parametrize(
    "error,reason",
    [
        (PchkAuthenticationError, "authentication_error"),
        (TimeoutError, "connection_refused"),
        (ConnectionRefusedError, "connection_refused"),
    ],
)
async def test_options_flow_error(hass, entry, error, reason):
    """Test config flow options."""
    entry.add_to_hass(hass)

    result = await hass.config_entries.options.async_init(entry.entry_id)
    await hass.async_block_till_done()

    assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
    assert result["step_id"] == "host_options"

    with patch(
        "pypck.connection.PchkConnectionManager.async_connect", side_effect=error
    ):
        result = await hass.config_entries.options.async_configure(
            result["flow_id"], user_input=OPTIONS.copy()
        )
        await hass.async_block_till_done()

        assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
        assert result["errors"] == {CONF_BASE: reason}


async def test_validate_connection(hass):
    """Test the connection validation."""
    data = CONNECTION_DATA.copy()
    data.pop(CONF_HOST)

    with patch("pypck.connection.PchkConnectionManager.async_connect") as async_connect:
        with patch("pypck.connection.PchkConnectionManager.async_close") as async_close:
            result = await validate_connection(CONNECTION_DATA[CONF_HOST], data=data)

    assert async_connect.is_called
    assert async_close.is_called
    assert result is None
