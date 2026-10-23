"""Test the Victron Modbus config flow."""

from collections.abc import Iterator
from contextlib import asynccontextmanager, contextmanager
from ipaddress import IPv4Address
from unittest.mock import AsyncMock, patch

from modbus_connection import ModbusTimeoutError
import pytest
from pytest_homeassistant.common import MockConfigEntry
from victron_modbus import UnsupportedDeviceError

from homeassistant.components.victron_modbus.const import DOMAIN
from homeassistant.config_entries import (
    SOURCE_IGNORE,
    SOURCE_USER,
    SOURCE_ZEROCONF,
    ConfigEntryState,
)
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.service_info.zeroconf import ZeroconfServiceInfo

from . import OTHER_SERIAL, SERIAL, VM_3P75CT, set_identity

pytestmark = pytest.mark.usefixtures("mock_setup_entry")

HOST = "192.168.1.101"

# Errors identifying a device, and the reason each one is shown as.
IDENTIFY_ERRORS = pytest.mark.parametrize(
    ("error", "reason"),
    [
        (ModbusTimeoutError(), "cannot_connect"),
        (HomeAssistantError("in use"), "cannot_connect"),
        (UnsupportedDeviceError(0xA389), "unsupported_device"),
        (RuntimeError("boom"), "unknown"),
    ],
)


def _discovery(
    host: str = HOST, service_type: str = "_victron-energy-meter._udp.local."
) -> ZeroconfServiceInfo:
    return ZeroconfServiceInfo(
        ip_address=IPv4Address(host),
        ip_addresses=[IPv4Address(host)],
        hostname="device.local.",
        name=f"Device-XYZ.{service_type}",
        port=502,
        type=service_type,
        properties={},
    )


def _failing_identify(error: Exception):
    return patch(
        "homeassistant.components.victron_modbus.config_flow.async_identify",
        side_effect=error,
    )


@contextmanager
def _devices_at(
    mock_unit, *, down: tuple[str, ...] = (), replaced: tuple[str, ...] = ()
) -> Iterator[list[str]]:
    """Answer for the fake unit at every address, noting the addresses probed.

    The devices at the addresses in ``down`` don't answer, and the ones at the
    addresses in ``replaced`` answer as another device.
    """
    probed: list[str] = []

    @asynccontextmanager
    async def _temporary_unit(hass: HomeAssistant, params, unit_id):
        probed.append(params.host)
        if params.host in down:
            raise ModbusTimeoutError
        serial = OTHER_SERIAL if params.host in replaced else SERIAL
        set_identity(mock_unit, VM_3P75CT, serial=serial)
        yield mock_unit

    with patch(
        "homeassistant.components.victron_modbus.config_flow.async_get_temporary_unit",
        side_effect=_temporary_unit,
    ):
        yield probed


async def test_user_flow(
    hass: HomeAssistant, mock_unit, mock_setup_entry: AsyncMock
) -> None:
    """The model and serial number are read from the device."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {}

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"host": HOST}
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == f"VM-3P75CT ({SERIAL})"
    assert result["data"] == {"host": HOST, "model": "vm_3p75ct"}
    assert result["result"].unique_id == SERIAL
    assert len(mock_setup_entry.mock_calls) == 1


@IDENTIFY_ERRORS
async def test_user_flow_errors(
    hass: HomeAssistant, mock_unit, error: Exception, reason: str
) -> None:
    """An identification error is shown, and the flow recovers from it."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    with _failing_identify(error):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {"host": HOST}
        )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": reason}

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"host": HOST}
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY


async def test_user_flow_no_serial(hass: HomeAssistant, mock_unit) -> None:
    """A device without a serial number can't be told apart, so is refused."""
    set_identity(mock_unit, VM_3P75CT, serial="")

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"host": HOST}
    )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "no_serial"}

    set_identity(mock_unit, VM_3P75CT)
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"host": HOST}
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY


async def test_user_flow_already_configured(
    hass: HomeAssistant, mock_unit, mock_config_entry: MockConfigEntry
) -> None:
    """The same device at a second address is refused, leaving the entry as is."""
    mock_config_entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"host": "192.168.1.110"}
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"
    assert mock_config_entry.data["host"] == HOST


@pytest.mark.parametrize(
    ("service_type", "product_id", "model", "name"),
    [
        ("_victron-energy-meter._udp.local.", 0xA1B1, "vm_3p75ct", "VM-3P75CT"),
        ("_victron-energy-meter._udp.local.", 0xA1B5, "vm_3p75ct", "VM-3P75CT"),
        ("_victron-energy-meter._udp.local.", 0xA1B2, "vm_3p5a", "VM-3P5A"),
        ("_victron-p1link._udp.local.", 0xC02F, "p1link", "P1Link"),
    ],
)
async def test_zeroconf_flow(
    hass: HomeAssistant,
    mock_unit,
    mock_setup_entry: AsyncMock,
    service_type: str,
    product_id: int,
    model: str,
    name: str,
) -> None:
    """A discovered device is identified by its product ID and confirmed."""
    set_identity(mock_unit, product_id)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_ZEROCONF}, data=_discovery(HOST, service_type)
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "confirm"
    assert result["description_placeholders"] == {"model": name, "host": HOST}
    # The discovered card shows the serial number, to tell devices apart.
    flow = hass.config_entries.flow.async_get(result["flow_id"])
    assert flow["context"]["title_placeholders"] == {"name": f"{name} ({SERIAL})"}

    result = await hass.config_entries.flow.async_configure(result["flow_id"], {})

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == f"{name} ({SERIAL})"
    assert result["data"] == {"host": HOST, "model": model}
    assert result["result"].unique_id == SERIAL
    assert len(mock_setup_entry.mock_calls) == 1


@IDENTIFY_ERRORS
async def test_zeroconf_flow_errors(
    hass: HomeAssistant, mock_unit, error: Exception, reason: str
) -> None:
    """A discovered device that can't be identified aborts."""
    with _failing_identify(error):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": SOURCE_ZEROCONF}, data=_discovery()
        )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == reason


async def test_zeroconf_flow_no_serial(hass: HomeAssistant, mock_unit) -> None:
    """A discovered device without a serial number can't be set up."""
    set_identity(mock_unit, VM_3P75CT, serial="")

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_ZEROCONF},
        data=_discovery(service_type="_victron-energy-meter._udp.local."),
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "no_serial"


async def test_zeroconf_flow_known_device_at_its_address(
    hass: HomeAssistant, mock_unit, mock_config_entry: MockConfigEntry
) -> None:
    """Rediscovering a device at its configured address changes nothing."""
    mock_config_entry.add_to_hass(hass)

    with _devices_at(mock_unit) as probed:
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": SOURCE_ZEROCONF}, data=_discovery()
        )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"
    assert probed == [HOST]
    assert mock_config_entry.data["host"] == HOST


async def _discover(hass: HomeAssistant, host: str):
    return await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_ZEROCONF}, data=_discovery(host)
    )


@pytest.mark.parametrize(
    "stored_host", [HOST, "meter.local"], ids=["address", "hostname"]
)
async def test_zeroconf_flow_keeps_host_that_still_answers(
    hass: HomeAssistant,
    mock_unit,
    mock_config_entry: MockConfigEntry,
    mock_setup_entry: AsyncMock,
    stored_host: str,
) -> None:
    """A device announced at a second address stays where it is while it answers."""
    mock_config_entry.add_to_hass(hass)
    hass.config_entries.async_update_entry(
        mock_config_entry, data={**mock_config_entry.data, "host": stored_host}
    )
    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)

    with _devices_at(mock_unit) as probed:
        result = await _discover(hass, "192.168.1.110")
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"
    assert probed == ["192.168.1.110", stored_host]
    assert mock_config_entry.data["host"] == stored_host
    assert len(mock_setup_entry.mock_calls) == 1


@pytest.mark.parametrize(
    ("down", "replaced"),
    [((HOST,), ()), ((), (HOST,))],
    ids=["no_answer", "other_device"],
)
async def test_zeroconf_flow_updates_host_that_stopped_answering(
    hass: HomeAssistant,
    mock_unit,
    mock_config_entry: MockConfigEntry,
    mock_setup_entry: AsyncMock,
    down: tuple[str, ...],
    replaced: tuple[str, ...],
) -> None:
    """The entry moves to the announced address once its own has stopped working."""
    mock_config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)

    with _devices_at(mock_unit, down=down, replaced=replaced) as probed:
        result = await _discover(hass, "192.168.1.110")
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"
    assert probed == ["192.168.1.110", HOST]
    assert mock_config_entry.data["host"] == "192.168.1.110"
    assert len(mock_setup_entry.mock_calls) == 2  # reloaded


async def test_zeroconf_flow_restarts_setup_of_refused_entry(
    hass: HomeAssistant, mock_unit, mock_config_entry: MockConfigEntry
) -> None:
    """An entry refused for finding another device at its address is set up again."""
    mock_config_entry.add_to_hass(hass)
    mock_config_entry.mock_state(hass, ConfigEntryState.SETUP_ERROR)

    with (
        _devices_at(mock_unit, replaced=(HOST,)),
        patch.object(hass.config_entries, "async_schedule_reload") as reload,
    ):
        result = await _discover(hass, "192.168.1.110")

    assert result["reason"] == "already_configured"
    assert mock_config_entry.data["host"] == "192.168.1.110"
    reload.assert_called_once_with(mock_config_entry.entry_id)


async def test_zeroconf_flow_follows_devices_that_swapped_addresses(
    hass: HomeAssistant,
    mock_unit,
    mock_config_entry: MockConfigEntry,
    mock_setup_entry: AsyncMock,
) -> None:
    """Two devices that exchange addresses each move their own entry."""
    other_host = "192.168.1.110"
    mock_config_entry.add_to_hass(hass)
    other_entry = MockConfigEntry(
        domain=DOMAIN,
        title=f"VM-3P75CT ({OTHER_SERIAL})",
        data={"host": other_host, "model": "vm_3p75ct"},
        unique_id=OTHER_SERIAL,
    )
    other_entry.add_to_hass(hass)

    # The first device now answers at the second one's address, and the second
    # device at the first one's.
    with _devices_at(mock_unit, replaced=(HOST,)):
        first = await _discover(hass, other_host)
        second = await _discover(hass, HOST)
    await hass.async_block_till_done()

    assert first["reason"] == second["reason"] == "already_configured"
    assert mock_config_entry.data["host"] == other_host
    assert other_entry.data["host"] == HOST


async def test_zeroconf_flow_ignored_device(hass: HomeAssistant, mock_unit) -> None:
    """A device the user ignored stays ignored, without probing its old address."""
    MockConfigEntry(
        domain=DOMAIN, source=SOURCE_IGNORE, unique_id=SERIAL, data={}
    ).add_to_hass(hass)

    with _devices_at(mock_unit) as probed:
        result = await _discover(hass, "192.168.1.110")

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"
    assert probed == ["192.168.1.110"]
