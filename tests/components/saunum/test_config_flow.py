"""Test the Saunum config flow."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

from pymodbus.exceptions import ModbusException
import pytest

from homeassistant import config_entries
from homeassistant.components.saunum.const import (
    CONF_SAUNA_TYPE_1_NAME,
    CONF_SAUNA_TYPE_2_NAME,
    CONF_SAUNA_TYPE_3_NAME,
    DEFAULT_SAUNA_TYPE_2_NAME,
    DEFAULT_SAUNA_TYPE_3_NAME,
    DOMAIN,
)
from homeassistant.const import CONF_HOST, CONF_PORT
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from tests.common import MockConfigEntry

TEST_USER_INPUT = {CONF_HOST: "192.168.1.100", CONF_PORT: 502}


@pytest.mark.usefixtures("mock_modbus_client")
async def test_form(hass: HomeAssistant) -> None:
    """Test we get the form."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert not result["errors"]


@pytest.mark.usefixtures("mock_modbus_client")
async def test_form_success(hass: HomeAssistant) -> None:
    """Test successful form submission."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"

    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        TEST_USER_INPUT,
    )
    await hass.async_block_till_done()

    assert result2["type"] is FlowResultType.CREATE_ENTRY
    assert result2["title"] == "Saunum Leil Sauna"
    assert result2["data"] == TEST_USER_INPUT


async def test_form_connection_error(hass: HomeAssistant, mock_modbus_client) -> None:
    """Test connection error handling."""
    mock_modbus_client.connect = AsyncMock(return_value=False)
    mock_modbus_client.connected = False

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        TEST_USER_INPUT,
    )

    assert result2["type"] is FlowResultType.FORM
    assert result2["errors"] == {"base": "cannot_connect"}


async def test_form_modbus_error(hass: HomeAssistant, mock_modbus_client) -> None:
    """Test Modbus read error handling."""
    mock_response = MagicMock()
    mock_response.isError.return_value = True
    mock_modbus_client.read_holding_registers = AsyncMock(return_value=mock_response)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        TEST_USER_INPUT,
    )

    assert result2["type"] is FlowResultType.FORM
    assert result2["errors"] == {"base": "cannot_connect"}


async def test_form_modbus_exception(hass: HomeAssistant, mock_modbus_client) -> None:
    """Test ModbusException handling."""
    mock_modbus_client.connect.side_effect = ModbusException("Modbus error")

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        TEST_USER_INPUT,
    )

    assert result2["type"] is FlowResultType.FORM
    assert result2["errors"] == {"base": "cannot_connect"}


async def test_form_exception(hass: HomeAssistant, mock_modbus_client) -> None:
    """Test exception handling."""
    mock_modbus_client.connect.side_effect = Exception("Connection failed")

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        TEST_USER_INPUT,
    )

    assert result2["type"] is FlowResultType.FORM
    assert result2["errors"] == {"base": "unknown"}


async def test_form_duplicate(hass: HomeAssistant) -> None:
    """Test duplicate entry handling."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data=TEST_USER_INPUT,
        # Config flow sets unique_id as "{host}:{port}" so mirror that here
        unique_id="192.168.1.100:502",
    )
    entry.add_to_hass(hass)

    with patch(
        "homeassistant.components.saunum.config_flow.AsyncModbusTcpClient"
    ) as mock_client_class:
        mock_client = mock_client_class.return_value
        mock_client.connected = True
        mock_client.connect = AsyncMock(return_value=True)
        mock_client.close = MagicMock()

        # Mock successful register read for config flow test
        mock_response = MagicMock()
        mock_response.isError.return_value = False
        mock_response.registers = [0]  # Session not active
        mock_client.read_holding_registers = AsyncMock(return_value=mock_response)

        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )

        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            TEST_USER_INPUT,
        )

        assert result2["type"] is FlowResultType.ABORT
        assert result2["reason"] == "already_configured"


async def test_options_flow_form_defaults(hass: HomeAssistant) -> None:
    """Test options flow form shows defaults for missing custom names."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data=TEST_USER_INPUT,
        unique_id="192.168.1.100:502",
        options={
            # Provide only type 1 name so type 2/3 fall back to defaults
            CONF_SAUNA_TYPE_1_NAME: "Calm",
        },
    )
    entry.add_to_hass(hass)

    # Init options flow
    result = await hass.config_entries.options.async_init(entry.entry_id)
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "init"

    # The schema object contains defaults; we can attempt validation to ensure
    # our provided type 1 value is preserved while others fallback.
    schema = result["data_schema"]
    validated = schema(
        {
            CONF_SAUNA_TYPE_1_NAME: "Calm",  # user leaves others unchanged
            CONF_SAUNA_TYPE_2_NAME: DEFAULT_SAUNA_TYPE_2_NAME,
            CONF_SAUNA_TYPE_3_NAME: DEFAULT_SAUNA_TYPE_3_NAME,
        }
    )
    assert validated[CONF_SAUNA_TYPE_1_NAME] == "Calm"
    assert validated[CONF_SAUNA_TYPE_2_NAME] == DEFAULT_SAUNA_TYPE_2_NAME
    assert validated[CONF_SAUNA_TYPE_3_NAME] == DEFAULT_SAUNA_TYPE_3_NAME


async def test_options_flow_submit_updates_entry(hass: HomeAssistant) -> None:
    """Test submitting options flow updates config entry options."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data=TEST_USER_INPUT,
        unique_id="192.168.1.100:502",
        options={},
    )
    entry.add_to_hass(hass)

    result = await hass.config_entries.options.async_init(entry.entry_id)
    assert result["type"] is FlowResultType.FORM

    new_options = {
        CONF_SAUNA_TYPE_1_NAME: "Relax",
        CONF_SAUNA_TYPE_2_NAME: "Energize",
        CONF_SAUNA_TYPE_3_NAME: "Intense",
    }
    result2 = await hass.config_entries.options.async_configure(
        result["flow_id"], user_input=new_options
    )
    assert result2["type"] is FlowResultType.CREATE_ENTRY
    assert entry.options[CONF_SAUNA_TYPE_1_NAME] == "Relax"
    assert entry.options[CONF_SAUNA_TYPE_2_NAME] == "Energize"
    assert entry.options[CONF_SAUNA_TYPE_3_NAME] == "Intense"
