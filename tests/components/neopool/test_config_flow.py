"""Test the NeoPool config flow."""

from unittest.mock import AsyncMock

from neopool_modbus.exceptions import (
    NeoPoolConnectionError,
    NeoPoolModbusError,
    NeoPoolTimeoutError,
)
import pytest

from homeassistant.components.neopool.const import (
    CONF_USE_LIGHT,
    DEFAULT_UNIT_ID,
    DOMAIN,
)
from homeassistant.config_entries import SOURCE_USER
from homeassistant.const import CONF_HOST, CONF_PORT
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from . import setup_integration
from .conftest import MOCK_HOST, MOCK_PORT, MOCK_SERIAL

from tests.common import MockConfigEntry

USER_INPUT = {
    CONF_HOST: MOCK_HOST,
    CONF_PORT: MOCK_PORT,
    "unit_id": DEFAULT_UNIT_ID,
    "modbus_framer": "tcp",
}


@pytest.mark.usefixtures("mock_neopool_client")
async def test_user_flow(
    hass: HomeAssistant,
    mock_setup_entry: AsyncMock,
) -> None:
    """Test a happy-path config flow creates the entry."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    assert not result["errors"]

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], USER_INPUT
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == MOCK_HOST
    assert result["data"][CONF_HOST] == MOCK_HOST
    assert result["data"][CONF_PORT] == MOCK_PORT
    assert result["result"].unique_id == MOCK_SERIAL
    assert mock_setup_entry.call_count == 1


@pytest.mark.parametrize(
    ("exc_cls", "error_key"),
    [
        (NeoPoolConnectionError, "cannot_connect"),
        (NeoPoolTimeoutError, "cannot_connect"),
        (NeoPoolModbusError, "cannot_read_modbus"),
    ],
)
async def test_user_flow_probe_errors_recover(
    hass: HomeAssistant,
    mock_setup_entry: AsyncMock,
    mock_socket_connection: AsyncMock,
    exc_cls: type[Exception],
    error_key: str,
) -> None:
    """Probe errors surface as form errors, and the flow recovers on retry."""
    mock_socket_connection.side_effect = exc_cls("boom")

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], USER_INPUT
    )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {CONF_HOST: error_key}

    mock_socket_connection.side_effect = None
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], USER_INPUT
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY


@pytest.mark.usefixtures("mock_neopool_client")
async def test_user_flow_already_configured(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test config flow aborts when the same device is already configured."""
    mock_config_entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], USER_INPUT
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


@pytest.mark.usefixtures("mock_neopool_client")
async def test_reconfigure_flow(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_setup_entry: AsyncMock,
) -> None:
    """A reconfigure flow updates the connection settings and reloads the entry."""
    mock_config_entry.add_to_hass(hass)

    result = await mock_config_entry.start_reconfigure_flow(hass)
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reconfigure"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {**USER_INPUT, CONF_HOST: "192.0.2.50", CONF_PORT: 1502},
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reconfigure_successful"
    assert mock_config_entry.data[CONF_HOST] == "192.0.2.50"
    assert mock_config_entry.data[CONF_PORT] == 1502


@pytest.mark.parametrize(
    ("exc_cls", "error_key"),
    [
        (NeoPoolConnectionError, "cannot_connect"),
        (NeoPoolTimeoutError, "cannot_connect"),
        (NeoPoolModbusError, "cannot_read_modbus"),
    ],
)
async def test_reconfigure_flow_probe_errors_recover(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_setup_entry: AsyncMock,
    mock_socket_connection: AsyncMock,
    exc_cls: type[Exception],
    error_key: str,
) -> None:
    """Probe errors surface as form errors, and the flow recovers on retry."""
    mock_config_entry.add_to_hass(hass)
    result = await mock_config_entry.start_reconfigure_flow(hass)

    mock_socket_connection.side_effect = exc_cls("boom")
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {**USER_INPUT, CONF_HOST: "192.0.2.50"},
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {CONF_HOST: error_key}

    mock_socket_connection.side_effect = None
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {**USER_INPUT, CONF_HOST: "192.0.2.50"},
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reconfigure_successful"


async def test_reconfigure_flow_serial_mismatch(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_setup_entry: AsyncMock,
    mock_socket_connection: AsyncMock,
) -> None:
    """A reconfigure targeting a different physical controller is rejected."""
    mock_config_entry.add_to_hass(hass)
    result = await mock_config_entry.start_reconfigure_flow(hass)

    mock_socket_connection.return_value = "9999999999"
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {**USER_INPUT, CONF_HOST: "192.0.2.50"},
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "serial_mismatch"


@pytest.mark.usefixtures("mock_neopool_client")
async def test_options_flow_show_form(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Opening the options flow shows the init form."""
    await setup_integration(hass, mock_config_entry)

    result = await hass.config_entries.options.async_init(mock_config_entry.entry_id)
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "init"


@pytest.mark.usefixtures("mock_neopool_client")
async def test_options_flow_save_changes(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Submitting the form persists the new option on the config entry."""
    await setup_integration(hass, mock_config_entry)

    result = await hass.config_entries.options.async_init(mock_config_entry.entry_id)
    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        {CONF_USE_LIGHT: True},
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert mock_config_entry.options[CONF_USE_LIGHT] is True

    await hass.config_entries.async_unload(mock_config_entry.entry_id)
    await hass.async_block_till_done()
