"""Tests for the Trovis 557x config flow."""

from modbus_connection.mock import MockModbusConnection

from homeassistant.components.trovis557x.const import (
    CONF_CONNECTION,
    CONF_UNIT_ID,
    DOMAIN,
)
from homeassistant.config_entries import SOURCE_USER
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from .conftest import UNIT_ID

from tests.common import MockConfigEntry


async def test_user_flow_titles_from_model(
    hass: HomeAssistant, connection_entry: MockConfigEntry
) -> None:
    """Picking a connection + unit reads the model and creates the entry."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_CONNECTION: connection_entry.entry_id, CONF_UNIT_ID: UNIT_ID},
    )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "Trovis 5579"  # read from the device
    assert result["data"][CONF_CONNECTION] == connection_entry.entry_id
    assert result["data"][CONF_UNIT_ID] == UNIT_ID


async def test_user_flow_cannot_connect(
    hass: HomeAssistant,
    connection_entry: MockConfigEntry,
    mock_modbus_connection: MockModbusConnection,
) -> None:
    """A dropped connection during validation surfaces cannot_connect."""
    await mock_modbus_connection.close()

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_CONNECTION: connection_entry.entry_id, CONF_UNIT_ID: UNIT_ID},
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "cannot_connect"}
