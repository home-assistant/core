"""Tests for the IONT config flow."""

from unittest.mock import AsyncMock, MagicMock, patch

from modbus_connection import ModbusTimeoutError
from modbus_connection.encode import encode_int
from modbus_connection.mock import MockModbusUnit
import pytest

from homeassistant.components.iont.const import DOMAIN
from homeassistant.config_entries import SOURCE_USER
from homeassistant.const import CONF_HOST, CONF_PORT
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.exceptions import HomeAssistantError

from . import (
    CONNECTOR_COUNT_REGISTER,
    MOCK_HOST,
    MOCK_PORT,
    MOCK_TITLE,
    MOCK_USER_INPUT,
)

from tests.common import MockConfigEntry

OTHER_HOST = "192.168.1.61"

pytestmark = pytest.mark.usefixtures("mock_setup_entry")


async def _start_user_flow(hass: HomeAssistant) -> str:
    """Open the flow and return its ID."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    assert result["errors"] == {}
    return result["flow_id"]


async def test_user_flow(hass: HomeAssistant) -> None:
    """A charger on the network is probed and its entry created."""
    flow_id = await _start_user_flow(hass)

    result = await hass.config_entries.flow.async_configure(flow_id, MOCK_USER_INPUT)
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == MOCK_TITLE
    assert result["data"] == MOCK_USER_INPUT
    assert result["result"].unique_id is None


async def test_user_flow_normalizes_the_host(hass: HomeAssistant) -> None:
    """A hostname is stored in one spelling, since a connection is shared by it."""
    flow_id = await _start_user_flow(hass)

    result = await hass.config_entries.flow.async_configure(
        flow_id, {CONF_HOST: "Charger.LOCAL", CONF_PORT: MOCK_PORT}
    )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"] == {CONF_HOST: "charger.local", CONF_PORT: MOCK_PORT}


async def test_user_flow_cannot_connect(
    hass: HomeAssistant, mock_modbus_unit: MockModbusUnit
) -> None:
    """An unresponsive device surfaces cannot_connect, then the flow recovers."""
    mock_modbus_unit.fail_requests(ModbusTimeoutError("timed out"))

    flow_id = await _start_user_flow(hass)
    result = await hass.config_entries.flow.async_configure(flow_id, MOCK_USER_INPUT)

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "cannot_connect"}

    # The charger answers again.
    mock_modbus_unit.fail_requests(None)

    result = await hass.config_entries.flow.async_configure(flow_id, MOCK_USER_INPUT)
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == MOCK_TITLE


async def test_user_flow_link_settings_in_use(hass: HomeAssistant) -> None:
    """A device already held over other link settings cannot be probed."""
    refuse = MagicMock()
    refuse.return_value.__aenter__ = AsyncMock(side_effect=HomeAssistantError("in use"))
    refuse.return_value.__aexit__ = AsyncMock(return_value=False)

    flow_id = await _start_user_flow(hass)
    with patch(
        "homeassistant.components.iont.config_flow.async_get_temporary_unit", refuse
    ):
        result = await hass.config_entries.flow.async_configure(
            flow_id, MOCK_USER_INPUT
        )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "cannot_connect"}


async def test_user_flow_no_iont_charger(
    hass: HomeAssistant, mock_modbus_unit: MockModbusUnit
) -> None:
    """A Modbus device that is not an IONT charger is rejected, then recovers."""
    mock_modbus_unit.input[CONNECTOR_COUNT_REGISTER] = encode_int(0, count=2)

    flow_id = await _start_user_flow(hass)
    result = await hass.config_entries.flow.async_configure(flow_id, MOCK_USER_INPUT)

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "no_iont_charger"}

    # The right device is at that address after all.
    mock_modbus_unit.input[CONNECTOR_COUNT_REGISTER] = encode_int(1, count=2)

    result = await hass.config_entries.flow.async_configure(flow_id, MOCK_USER_INPUT)
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY


async def test_user_flow_already_configured(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Setting up the same address twice aborts."""
    mock_config_entry.add_to_hass(hass)

    flow_id = await _start_user_flow(hass)
    result = await hass.config_entries.flow.async_configure(
        flow_id, {CONF_HOST: MOCK_HOST.upper(), CONF_PORT: MOCK_PORT}
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


async def test_reconfigure_flow(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """The charger can be reconfigured to a new address."""
    mock_config_entry.add_to_hass(hass)

    result = await mock_config_entry.start_reconfigure_flow(hass)
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reconfigure"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_HOST: OTHER_HOST, CONF_PORT: 1502}
    )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reconfigure_successful"
    assert mock_config_entry.data == {CONF_HOST: OTHER_HOST, CONF_PORT: 1502}


async def test_reconfigure_flow_cannot_connect(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_modbus_unit: MockModbusUnit,
) -> None:
    """A reconfigure attempt surfaces cannot_connect, then recovers."""
    mock_config_entry.add_to_hass(hass)
    mock_modbus_unit.fail_requests(ModbusTimeoutError("timed out"))

    result = await mock_config_entry.start_reconfigure_flow(hass)
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_HOST: OTHER_HOST, CONF_PORT: MOCK_PORT}
    )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "cannot_connect"}

    mock_modbus_unit.fail_requests(None)

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_HOST: OTHER_HOST, CONF_PORT: MOCK_PORT}
    )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reconfigure_successful"
    assert mock_config_entry.data[CONF_HOST] == OTHER_HOST


async def test_reconfigure_flow_onto_another_entry_aborts(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Reconfiguring onto an address another entry already uses aborts."""
    mock_config_entry.add_to_hass(hass)
    other = MockConfigEntry(
        domain=DOMAIN,
        title=MOCK_TITLE,
        data={CONF_HOST: OTHER_HOST, CONF_PORT: MOCK_PORT},
    )
    other.add_to_hass(hass)

    result = await mock_config_entry.start_reconfigure_flow(hass)
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_HOST: OTHER_HOST, CONF_PORT: MOCK_PORT}
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"
    assert mock_config_entry.data[CONF_HOST] == MOCK_HOST
