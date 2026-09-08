"""Test the Flexit config flow."""

from unittest.mock import AsyncMock, MagicMock, patch

from modbus_connection import ModbusError, ModbusTcpParams
from modbus_connection.mock import MockModbusUnit
import pytest

from homeassistant.components.flexit.const import (
    CONF_BAUDRATE,
    CONF_UNIT,
    DOMAIN,
    TYPE_TCP,
)
from homeassistant.config_entries import (
    SOURCE_RECONFIGURE,
    SOURCE_USER,
    ConfigEntryState,
)
from homeassistant.const import CONF_DEVICE, CONF_HOST, CONF_PORT, CONF_TYPE
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType, InvalidData
from homeassistant.exceptions import HomeAssistantError

from tests.common import MockConfigEntry

TCP_USER_INPUT = {CONF_HOST: "1.1.1.1", CONF_PORT: 502, CONF_UNIT: 1}
TCP_ENTRY_DATA = {CONF_TYPE: TYPE_TCP, **TCP_USER_INPUT}
TCP_RECONFIGURE_INPUT = {CONF_HOST: "2.2.2.2", CONF_PORT: 502, CONF_UNIT: 1}

SERIAL_USER_INPUT = {
    CONF_DEVICE: "/dev/ttyUSB0",
    "baudrate": 57600,
    CONF_UNIT: 1,
}
SERIAL_ENTRY_DATA = {CONF_TYPE: "serial", **SERIAL_USER_INPUT}


async def test_full_flow(
    hass: HomeAssistant, mock_get_temporary_modbus_unit: MagicMock
) -> None:
    """Test the full TCP flow."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] is FlowResultType.MENU
    assert result["step_id"] == "user"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"next_step_id": "tcp"}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "tcp"
    assert result["errors"] == {}

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        TCP_USER_INPUT,
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "Flexit"
    assert result["data"] == TCP_ENTRY_DATA
    mock_get_temporary_modbus_unit.assert_called_once_with(
        hass, ModbusTcpParams(host="1.1.1.1", port=502), 1
    )


async def test_tcp_host_is_normalized(hass: HomeAssistant) -> None:
    """Test TCP hosts are stored in lowercase."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"next_step_id": "tcp"}
    )

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {**TCP_USER_INPUT, CONF_HOST: "Device.Local"}
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"][CONF_HOST] == "device.local"


async def test_maximum_unit(hass: HomeAssistant) -> None:
    """Test the maximum Modbus unit ID is accepted."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"next_step_id": "tcp"}
    )

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {**TCP_USER_INPUT, CONF_UNIT: 247}
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"][CONF_UNIT] == 247


@pytest.mark.parametrize("unit", [0, 248])
async def test_unit_out_of_range(hass: HomeAssistant, unit: int) -> None:
    """Test unit IDs outside the Modbus address range are rejected."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"next_step_id": "tcp"}
    )

    with pytest.raises(InvalidData):
        await hass.config_entries.flow.async_configure(
            result["flow_id"], {**TCP_USER_INPUT, CONF_UNIT: unit}
        )


async def test_full_flow_serial(
    hass: HomeAssistant,
) -> None:
    """Test the full serial (RTU) flow."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] is FlowResultType.MENU

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"next_step_id": "serial"}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "serial"
    assert result["errors"] == {}
    assert (
        result["data_schema"]({CONF_DEVICE: "/dev/ttyUSB0", CONF_UNIT: 1})[
            CONF_BAUDRATE
        ]
        == 9600
    )

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        SERIAL_USER_INPUT,
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "Flexit"
    assert result["data"] == SERIAL_ENTRY_DATA


async def test_form_cannot_connect_and_retry(
    hass: HomeAssistant,
    mock_modbus_unit: MockModbusUnit,
) -> None:
    """Test we handle a connect error, then allow retrying successfully."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"next_step_id": "tcp"}
    )

    mock_modbus_unit.fail_requests(ModbusError("update failed"))

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        TCP_USER_INPUT,
    )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "cannot_connect"}

    mock_modbus_unit.fail_requests(None)

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        TCP_USER_INPUT,
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY


async def test_form_cannot_read_device(
    hass: HomeAssistant,
    mock_modbus_unit: MockModbusUnit,
) -> None:
    """Test we handle a device that cannot be read while validating the flow."""
    mock_modbus_unit.fail_requests(ModbusError("update failed"))

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"next_step_id": "tcp"}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        TCP_USER_INPUT,
    )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "cannot_connect"}


async def test_form_shared_link_conflict(
    hass: HomeAssistant,
    mock_get_temporary_modbus_unit: MagicMock,
) -> None:
    """Test an incompatible shared connection is a connection error."""
    mock_get_temporary_modbus_unit.side_effect = HomeAssistantError

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"next_step_id": "tcp"}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], TCP_USER_INPUT
    )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "cannot_connect"}


async def test_form_unknown_exception(
    hass: HomeAssistant,
    mock_get_temporary_modbus_unit: MagicMock,
) -> None:
    """Test we handle unknown exception."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"next_step_id": "tcp"}
    )

    temporary_unit = mock_get_temporary_modbus_unit.side_effect
    mock_get_temporary_modbus_unit.side_effect = Exception

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        TCP_USER_INPUT,
    )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "unknown"}

    mock_get_temporary_modbus_unit.side_effect = temporary_unit

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        TCP_USER_INPUT,
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY


async def test_reconfigure_flow(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test reconfiguration flow."""
    mock_config_entry.add_to_hass(hass)
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_RECONFIGURE, "entry_id": mock_config_entry.entry_id},
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reconfigure"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        TCP_RECONFIGURE_INPUT,
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reconfigure_successful"
    assert mock_config_entry.data[CONF_HOST] == "2.2.2.2"


async def test_reconfigure_flow_serial(
    hass: HomeAssistant,
    mock_serial_config_entry: MockConfigEntry,
) -> None:
    """Test reconfiguration flow for a serial connection."""
    mock_serial_config_entry.add_to_hass(hass)
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={
            "source": SOURCE_RECONFIGURE,
            "entry_id": mock_serial_config_entry.entry_id,
        },
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reconfigure"

    new_input = {**SERIAL_USER_INPUT, CONF_DEVICE: "/dev/ttyUSB1"}
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        new_input,
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reconfigure_successful"
    assert mock_serial_config_entry.data[CONF_DEVICE] == "/dev/ttyUSB1"


async def test_reconfigure_loaded_entry_releases_connection(
    hass: HomeAssistant,
    mock_serial_config_entry: MockConfigEntry,
) -> None:
    """Test reconfiguration releases the active connection before validation."""
    mock_serial_config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(mock_serial_config_entry.entry_id)

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={
            "source": SOURCE_RECONFIGURE,
            "entry_id": mock_serial_config_entry.entry_id,
        },
    )

    async def check_connection_after_unload(*_: object) -> None:
        assert mock_serial_config_entry.state is not ConfigEntryState.LOADED

    with patch(
        "homeassistant.components.flexit.config_flow.check_connection",
        AsyncMock(side_effect=check_connection_after_unload),
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {**SERIAL_USER_INPUT, "baudrate": 38400}
        )

    assert result["type"] is FlowResultType.ABORT


async def test_reconfigure_loaded_entry_restored_after_error(
    hass: HomeAssistant,
    mock_serial_config_entry: MockConfigEntry,
) -> None:
    """Test failed reconfiguration restores the active connection."""
    mock_serial_config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(mock_serial_config_entry.entry_id)

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={
            "source": SOURCE_RECONFIGURE,
            "entry_id": mock_serial_config_entry.entry_id,
        },
    )

    with patch(
        "homeassistant.components.flexit.config_flow.check_connection",
        AsyncMock(return_value="cannot_connect"),
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {**SERIAL_USER_INPUT, "baudrate": 38400}
        )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "cannot_connect"}
    assert mock_serial_config_entry.state is ConfigEntryState.LOADED


async def test_reconfigure_stops_when_unload_fails(
    hass: HomeAssistant,
    mock_serial_config_entry: MockConfigEntry,
) -> None:
    """Test reconfiguration stops when the active entry cannot unload."""
    mock_serial_config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(mock_serial_config_entry.entry_id)

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={
            "source": SOURCE_RECONFIGURE,
            "entry_id": mock_serial_config_entry.entry_id,
        },
    )

    with (
        patch.object(
            hass.config_entries, "async_unload", AsyncMock(return_value=False)
        ),
        patch(
            "homeassistant.components.flexit.config_flow.check_connection",
            AsyncMock(),
        ) as check_connection,
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {**SERIAL_USER_INPUT, "baudrate": 38400}
        )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "unknown"}
    check_connection.assert_not_awaited()


async def test_reconfigure_flow_errors(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_modbus_unit: MockModbusUnit,
) -> None:
    """Test error handling in reconfiguration flow."""
    mock_config_entry.add_to_hass(hass)
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_RECONFIGURE, "entry_id": mock_config_entry.entry_id},
    )
    assert result["type"] is FlowResultType.FORM

    mock_modbus_unit.fail_requests(ModbusError("update failed"))
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        TCP_RECONFIGURE_INPUT,
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "cannot_connect"}

    mock_modbus_unit.fail_requests(None)
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        TCP_RECONFIGURE_INPUT,
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reconfigure_successful"


async def test_reconfigure_flow_already_configured(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test reconfigure aborts if another entry already uses the given connection."""
    other_entry = MockConfigEntry(
        domain=DOMAIN,
        title="Flexit",
        data={CONF_TYPE: TYPE_TCP, **TCP_RECONFIGURE_INPUT},
        entry_id="flexit_002",
    )

    mock_config_entry.add_to_hass(hass)
    other_entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_RECONFIGURE, "entry_id": mock_config_entry.entry_id},
    )

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        TCP_RECONFIGURE_INPUT,
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


async def test_already_configured(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Test we handle already configured."""
    mock_config_entry.add_to_hass(hass)
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"next_step_id": "tcp"}
    )

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        TCP_USER_INPUT,
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


async def test_already_configured_host_case_insensitive(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Test hostname case differences cannot create duplicate entries."""
    mock_config_entry.add_to_hass(hass)
    hass.config_entries.async_update_entry(
        mock_config_entry, data={**mock_config_entry.data, CONF_HOST: "device.local"}
    )
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"next_step_id": "tcp"}
    )

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {**TCP_USER_INPUT, CONF_HOST: "Device.Local"}
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"
