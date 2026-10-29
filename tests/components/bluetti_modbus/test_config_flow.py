"""Tests for the BLUETTI Modbus config flow."""

from ipaddress import ip_address
from typing import Any
from unittest.mock import patch

from bluetti_modbus_lib import get_device
from modbus_connection import (
    AcknowledgeError,
    ModbusConnectionError,
    ModbusTimeoutError,
)
from modbus_connection.exceptions import IllegalDataAddressError
from modbus_connection.mock import MockModbusConnection, MockModbusUnit
import pytest
from pytest_homeassistant.common import MockConfigEntry

from homeassistant.components.bluetti_modbus.const import CONF_UNIT_ID, DOMAIN
from homeassistant.config_entries import (
    SOURCE_IGNORE,
    SOURCE_USER,
    SOURCE_ZEROCONF,
    ConfigEntryState,
)
from homeassistant.const import CONF_HOST, CONF_PORT
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.service_info.zeroconf import ZeroconfServiceInfo

from . import setup_integration
from .conftest import (
    HOST,
    PORT,
    SERIAL,
    SERIAL_ADDRESS,
    UNIT_ID,
    bluetti_data,
    seed_unit,
)

TITLE = "Balco 260"
NEW_HOST = "5.6.7.8"


def _user_input(host: str = HOST, unit_id: int = UNIT_ID) -> dict[str, Any]:
    """Form input for the user step."""
    return {
        CONF_HOST: host,
        CONF_PORT: PORT,
        CONF_UNIT_ID: unit_id,
    }


async def test_user_flow(hass: HomeAssistant, mock_modbus_unit: MockModbusUnit) -> None:
    """A device on the network is probed and its entry created."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    flow_id = result["flow_id"]

    result = await hass.config_entries.flow.async_configure(flow_id, _user_input())
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == TITLE
    assert result["data"] == bluetti_data()
    assert result["result"].unique_id == SERIAL


@pytest.mark.parametrize(
    ("request_error", "teardown_error"),
    [
        pytest.param(ModbusTimeoutError("timed out"), None, id="timeout"),
        pytest.param(TimeoutError("timed out"), None, id="bare_timeout"),
        pytest.param(AcknowledgeError(), None, id="still_busy"),
        pytest.param(
            ModbusTimeoutError("timed out"),
            ModbusConnectionError("teardown failed"),
            id="teardown_fails",
        ),
    ],
)
async def test_user_flow_cannot_connect(
    hass: HomeAssistant,
    mock_modbus_unit: MockModbusUnit,
    request_error: Exception,
    teardown_error: Exception | None,
) -> None:
    """A device that can't be read surfaces cannot_connect, then the flow recovers."""
    mock_modbus_unit.fail_requests(request_error)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    flow_id = result["flow_id"]
    with patch.object(mock_modbus_unit, "disconnect", side_effect=teardown_error):
        result = await hass.config_entries.flow.async_configure(flow_id, _user_input())

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "cannot_connect"}

    mock_modbus_unit.fail_requests(None)
    result = await hass.config_entries.flow.async_configure(flow_id, _user_input())
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY


async def test_user_flow_unexpected_error(
    hass: HomeAssistant, mock_modbus_unit: MockModbusUnit
) -> None:
    """An unexpected probe failure surfaces unknown, then the flow recovers."""
    mock_modbus_unit.fail_requests(ValueError("unexpected"))

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    flow_id = result["flow_id"]
    result = await hass.config_entries.flow.async_configure(flow_id, _user_input())

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "unknown"}

    mock_modbus_unit.fail_requests(None)
    result = await hass.config_entries.flow.async_configure(flow_id, _user_input())
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY


async def test_user_flow_rejects_a_zero_serial(
    hass: HomeAssistant, mock_modbus_unit: MockModbusUnit
) -> None:
    """A responder reporting serial 0 is rejected, then the flow recovers."""
    mock_modbus_unit.holding[SERIAL_ADDRESS] = 0

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    flow_id = result["flow_id"]
    result = await hass.config_entries.flow.async_configure(flow_id, _user_input())

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "invalid_serial"}

    mock_modbus_unit.holding[SERIAL_ADDRESS] = int(SERIAL)
    result = await hass.config_entries.flow.async_configure(flow_id, _user_input())
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY


async def test_user_flow_retries_a_transient_busy_response(
    hass: HomeAssistant, mock_modbus_unit: MockModbusUnit
) -> None:
    """A device that asks for a retry once during the probe does not fail it."""
    read_holding_registers = mock_modbus_unit.read_holding_registers
    attempts = 0

    async def busy_once(address: int, count: int) -> list[int]:
        nonlocal attempts
        attempts += 1
        if attempts == 1:
            raise AcknowledgeError
        return await read_holding_registers(address, count)

    with patch.object(mock_modbus_unit, "read_holding_registers", busy_once):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": SOURCE_USER}
        )
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], _user_input()
        )
        await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["result"].unique_id == SERIAL


async def test_user_flow_unsupported_device(
    hass: HomeAssistant, mock_modbus_unit: MockModbusUnit
) -> None:
    """A device reporting another model is rejected, then the flow recovers."""
    field = get_device("balco260").get_field("d_inverter_type")
    assert field is not None
    balco260_words = field.encode("Balco260")
    for offset, word in enumerate(field.encode("EP2000")):
        mock_modbus_unit.holding[field.address + offset] = word

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    flow_id = result["flow_id"]
    result = await hass.config_entries.flow.async_configure(flow_id, _user_input())

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "unsupported_device"}

    for offset, word in enumerate(balco260_words):
        mock_modbus_unit.holding[field.address + offset] = word
    result = await hass.config_entries.flow.async_configure(flow_id, _user_input())
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY


class _ConflictingUnit:
    """An async context manager standing in for a claimed, incompatible link."""

    async def __aenter__(self) -> None:
        raise HomeAssistantError("already in use with different link settings")

    async def __aexit__(self, *exc_info: object) -> None:
        return None


async def test_user_flow_link_settings_in_use(
    hass: HomeAssistant, mock_modbus_unit: MockModbusUnit
) -> None:
    """A link already claimed with different settings recovers once it's free."""
    with patch(
        "homeassistant.components.bluetti_modbus.config_flow.async_get_temporary_unit",
        return_value=_ConflictingUnit(),
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": SOURCE_USER}
        )
        flow_id = result["flow_id"]
        result = await hass.config_entries.flow.async_configure(flow_id, _user_input())

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "link_settings_in_use"}

    result = await hass.config_entries.flow.async_configure(flow_id, _user_input())
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY


async def test_user_flow_already_configured(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_modbus_unit: MockModbusUnit,
) -> None:
    """Setting up the same host, port and unit id twice aborts, before any probe."""
    mock_config_entry.add_to_hass(hass)
    hass.config_entries.async_update_entry(
        mock_config_entry, unique_id="another-device"
    )
    # Offline: a probe would fail with cannot_connect, so it must not happen.
    mock_modbus_unit.fail_requests(ModbusTimeoutError("offline"))

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], _user_input()
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


async def test_user_flow_probes_only_the_fields_setup_reads(
    hass: HomeAssistant, mock_modbus_unit: MockModbusUnit
) -> None:
    """A register setup leaves out of its read plan is not read by the probe either."""
    fault = get_device("balco260").get_field("d_inverter_fault")
    assert fault is not None
    mock_modbus_unit.fail_read(fault.address, IllegalDataAddressError())

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], _user_input()
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["result"].unique_id == SERIAL


@pytest.mark.parametrize(
    ("host", "unit_id"),
    [
        pytest.param("5.6.7.8", UNIT_ID, id="other_address"),
        pytest.param(HOST, 2, id="other_device_id"),
    ],
)
async def test_user_flow_rejects_the_same_serial_at_a_different_endpoint(
    hass: HomeAssistant,
    mock_modbus_connection: MockModbusConnection,
    mock_config_entry: MockConfigEntry,
    host: str,
    unit_id: int,
) -> None:
    """The same device answering at a different address or device ID aborts."""
    mock_config_entry.add_to_hass(hass)
    seed_unit(mock_modbus_connection.for_unit(unit_id))

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], _user_input(host=host, unit_id=unit_id)
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


def _zeroconf_info(host: str = HOST) -> ZeroconfServiceInfo:
    """What a Balco 260 announces over mDNS."""
    return ZeroconfServiceInfo(
        ip_address=ip_address(host),
        ip_addresses=[ip_address(host)],
        hostname="blhems-1a2b3c4d5e6f.local.",
        name="Bluetti HEMS._http._tcp.local.",
        port=80,
        type="_http._tcp.local.",
        properties={"path": "/"},
    )


async def test_zeroconf_flow(
    hass: HomeAssistant, mock_modbus_unit: MockModbusUnit
) -> None:
    """A discovered power station is probed, confirmed and added."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_ZEROCONF}, data=_zeroconf_info()
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "zeroconf_confirm"
    assert (
        hass.config_entries.flow.async_get(result["flow_id"])["context"]["unique_id"]
        == SERIAL
    )

    result = await hass.config_entries.flow.async_configure(result["flow_id"], {})
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == TITLE
    assert result["data"] == bluetti_data()
    assert result["result"].unique_id == SERIAL


async def test_zeroconf_known_address_is_not_probed(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_modbus_unit: MockModbusUnit,
) -> None:
    """An address an entry already uses aborts without a Modbus read."""
    mock_config_entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_ZEROCONF}, data=_zeroconf_info()
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"
    assert not mock_modbus_unit.read_events


async def test_zeroconf_discovery_in_progress(
    hass: HomeAssistant, mock_modbus_unit: MockModbusUnit
) -> None:
    """A repeated announcement during a pending discovery aborts."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_ZEROCONF}, data=_zeroconf_info()
    )
    assert result["type"] is FlowResultType.FORM

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_ZEROCONF}, data=_zeroconf_info()
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_in_progress"


async def test_user_flow_replaces_a_pending_discovery(
    hass: HomeAssistant, mock_modbus_unit: MockModbusUnit
) -> None:
    """Adding a discovered power station by hand ends its pending discovery."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_ZEROCONF}, data=_zeroconf_info()
    )
    assert result["type"] is FlowResultType.FORM

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], _user_input(host=NEW_HOST)
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"] == {**bluetti_data(), CONF_HOST: NEW_HOST}
    assert result["result"].unique_id == SERIAL
    assert not hass.config_entries.flow.async_progress()


async def test_zeroconf_updates_a_moved_device(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_modbus_unit: MockModbusUnit,
) -> None:
    """The same power station announced at a new address updates its entry."""
    await setup_integration(hass, mock_config_entry)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_ZEROCONF}, data=_zeroconf_info(NEW_HOST)
    )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"
    assert mock_config_entry.data == {**bluetti_data(), CONF_HOST: NEW_HOST}
    assert mock_config_entry.state is ConfigEntryState.LOADED


@pytest.mark.parametrize(
    "entry_data",
    [
        pytest.param({CONF_PORT: 1502}, id="other_port"),
        pytest.param({CONF_UNIT_ID: 2}, id="other_device_id"),
    ],
)
async def test_zeroconf_leaves_an_entry_on_other_settings(
    hass: HomeAssistant,
    mock_modbus_unit: MockModbusUnit,
    entry_data: dict[str, Any],
) -> None:
    """An entry on another port or device ID keeps its host."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id=SERIAL,
        data={**bluetti_data(), CONF_HOST: "proxy.local", **entry_data},
    )
    entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_ZEROCONF}, data=_zeroconf_info()
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"
    assert entry.data == {**bluetti_data(), CONF_HOST: "proxy.local", **entry_data}


async def test_zeroconf_can_be_ignored(
    hass: HomeAssistant, mock_modbus_unit: MockModbusUnit
) -> None:
    """Ignoring a discovery stores the serial number."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_ZEROCONF}, data=_zeroconf_info()
    )
    assert result["type"] is FlowResultType.FORM

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_IGNORE},
        data={"unique_id": SERIAL, "title": TITLE},
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["result"].unique_id == SERIAL
    assert not hass.config_entries.flow.async_progress()


async def test_zeroconf_ignored_by_serial(
    hass: HomeAssistant, mock_modbus_unit: MockModbusUnit
) -> None:
    """A power station ignored under its serial number is not offered again."""
    MockConfigEntry(domain=DOMAIN, source=SOURCE_IGNORE, unique_id=SERIAL).add_to_hass(
        hass
    )

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_ZEROCONF}, data=_zeroconf_info()
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


async def test_zeroconf_cannot_connect(
    hass: HomeAssistant, mock_modbus_unit: MockModbusUnit
) -> None:
    """A discovered device that can't be read aborts with the probe's reason."""
    mock_modbus_unit.fail_requests(ModbusTimeoutError("timed out"))

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_ZEROCONF}, data=_zeroconf_info()
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "cannot_connect"


async def test_reconfigure_flow(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_modbus_unit: MockModbusUnit,
) -> None:
    """The entry is pointed at the address the same device moved to."""
    await setup_integration(hass, mock_config_entry)

    result = await mock_config_entry.start_reconfigure_flow(hass)
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reconfigure"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], _user_input(host=NEW_HOST)
    )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reconfigure_successful"
    assert mock_config_entry.data == {**bluetti_data(), CONF_HOST: NEW_HOST}
    assert mock_config_entry.state is ConfigEntryState.LOADED


async def test_reconfigure_flow_cannot_connect(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_modbus_unit: MockModbusUnit,
) -> None:
    """A device that can't be read surfaces cannot_connect, then the flow recovers."""
    await setup_integration(hass, mock_config_entry)

    result = await mock_config_entry.start_reconfigure_flow(hass)
    mock_modbus_unit.fail_requests(ModbusTimeoutError("timed out"))
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], _user_input(host=NEW_HOST)
    )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "cannot_connect"}

    mock_modbus_unit.fail_requests(None)
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], _user_input(host=NEW_HOST)
    )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reconfigure_successful"
    assert mock_config_entry.data[CONF_HOST] == NEW_HOST


async def test_reconfigure_flow_rejects_another_device(
    hass: HomeAssistant,
    mock_modbus_connection: MockModbusConnection,
    mock_config_entry: MockConfigEntry,
    mock_modbus_unit: MockModbusUnit,
) -> None:
    """A different serial at the new address aborts and leaves the entry as it was."""
    await setup_integration(hass, mock_config_entry)
    other = mock_modbus_connection.for_unit(2)
    seed_unit(other)
    other.holding[SERIAL_ADDRESS] = 5678

    result = await mock_config_entry.start_reconfigure_flow(hass)
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], _user_input(unit_id=2)
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "unique_id_mismatch"
    assert mock_config_entry.data == bluetti_data()
