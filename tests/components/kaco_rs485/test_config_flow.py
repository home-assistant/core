"""Test the KACO RS485 config flow.

Setup is a bus scan rather than a form, so most of this covers what the scan
found and how it is reported.
"""

from unittest.mock import AsyncMock, patch

from kaco_rs485 import BusError
from kaco_rs485.testing import BLUEPLANET, POWADOR_6400XI, CannedInverter, FakeBus
import pytest
from pytest_homeassistant.common import MockConfigEntry

from homeassistant.components.kaco_rs485.const import (
    CONF_ADDRESSES,
    CONF_INVERTERS,
    CONF_SW_VERSION,
    DOMAIN,
)
from homeassistant.config_entries import SOURCE_USER, ConfigFlowResult
from homeassistant.const import CONF_MODEL, CONF_PORT
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from . import MOCK_PORT, MOCK_PORT_DESCRIPTION

pytestmark = pytest.mark.usefixtures("mock_setup_entry")


async def _submit_port(
    hass: HomeAssistant, flow_id: str, port: str = MOCK_PORT
) -> ConfigFlowResult:
    """Submit the port, let the scan finish, and return the step after it."""
    result = await hass.config_entries.flow.async_configure(flow_id, {CONF_PORT: port})
    assert result["type"] is FlowResultType.SHOW_PROGRESS

    await hass.async_block_till_done()
    return await hass.config_entries.flow.async_configure(flow_id)


async def _scan(hass: HomeAssistant, port: str = MOCK_PORT) -> ConfigFlowResult:
    """Start the flow, submit the port, and return the step after the scan."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"

    return await _submit_port(hass, result["flow_id"], port)


@pytest.mark.usefixtures("mock_bus")
async def test_scan_finds_inverters_and_creates_an_entry(
    hass: HomeAssistant, mock_setup_entry: AsyncMock
) -> None:
    """Test the happy path: scan the bus, confirm what answered, create."""
    result = await _scan(hass)

    assert result["step_id"] == "confirm"
    assert result["description_placeholders"] == {
        "found": "1 — 6400xi, 2 — 6400xi, 4 — 8000xi"
    }

    # No input: every inverter found is kept, unwanted ones disabled later.
    assert result["data_schema"] is None
    result = await hass.config_entries.flow.async_configure(result["flow_id"], {})

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == MOCK_PORT_DESCRIPTION
    assert result["data"][CONF_PORT] == MOCK_PORT
    assert result["data"][CONF_ADDRESSES] == [1, 2, 4]
    # Recorded while the units are awake; they stop answering after dusk.
    assert result["data"][CONF_INVERTERS]["4"] == {
        CONF_MODEL: "8000xi",
        CONF_SW_VERSION: "K222.36DE 1C5F",
    }
    mock_setup_entry.assert_awaited_once()


async def test_a_bus_with_only_unsupported_units_says_so(
    hass: HomeAssistant, mock_bus: FakeBus
) -> None:
    """Test a blueplanet-only bus is told what answered, not to come back later."""
    mock_bus.silence(1, 2, 4)
    mock_bus.wake(3, BLUEPLANET)

    result = await _scan(hass)

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "only_unsupported"
    assert result["description_placeholders"]["unsupported"] == "3"


async def test_a_blueplanet_alongside_xi_units_is_simply_skipped(
    hass: HomeAssistant, mock_bus: FakeBus
) -> None:
    """Test extra devices do not interrupt a scan that found what it wanted."""
    mock_bus.wake(3, BLUEPLANET)

    result = await _scan(hass)

    assert result["step_id"] == "confirm"
    assert "3" not in result["description_placeholders"]["found"]

    result = await hass.config_entries.flow.async_configure(result["flow_id"], {})
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"][CONF_ADDRESSES] == [1, 2, 4]


async def test_a_bus_where_nothing_answers_aborts(
    hass: HomeAssistant, mock_bus: FakeBus
) -> None:
    """Test an empty scan refuses to create an entry."""
    mock_bus.silence(1, 2, 4)

    result = await _scan(hass)

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "no_inverters"


async def test_a_port_that_will_not_open_can_be_corrected(
    hass: HomeAssistant, mock_bus: FakeBus
) -> None:
    """Test the port is opened before scanning, so a bad one can be retried."""
    mock_bus.open_error = BusError("could not open /dev/ttyUSB0")

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_PORT: MOCK_PORT}
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    assert result["errors"] == {"base": "cannot_connect"}

    mock_bus.open_error = None
    result = await _submit_port(hass, result["flow_id"])
    assert result["step_id"] == "confirm"

    result = await hass.config_entries.flow.async_configure(result["flow_id"], {})
    assert result["type"] is FlowResultType.CREATE_ENTRY


async def test_a_port_that_dies_mid_scan_aborts(
    hass: HomeAssistant, mock_bus: FakeBus
) -> None:
    """Test a port lost after it opened ends the flow rather than hanging."""
    mock_bus.request_error = BusError("connection closed")

    result = await _scan(hass)

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "cannot_connect"


@pytest.mark.usefixtures("mock_bus")
async def test_a_port_already_configured_is_rejected(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Test the same port cannot be added twice; two masters corrupt the bus."""
    mock_config_entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_PORT: MOCK_PORT}
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


@pytest.mark.usefixtures("mock_bus")
async def test_a_port_added_by_another_flow_during_the_scan_is_rejected(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Test two flows on one port cannot both create an entry."""
    result = await _scan(hass)
    assert result["step_id"] == "confirm"

    mock_config_entry.add_to_hass(hass)
    result = await hass.config_entries.flow.async_configure(result["flow_id"], {})

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


@pytest.mark.usefixtures("mock_bus")
async def test_a_port_already_being_set_up_is_rejected(hass: HomeAssistant) -> None:
    """Test a second flow cannot scan a port another flow is scanning."""
    first = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    first = await hass.config_entries.flow.async_configure(
        first["flow_id"], {CONF_PORT: MOCK_PORT}
    )
    assert first["type"] is FlowResultType.SHOW_PROGRESS

    second = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    second = await hass.config_entries.flow.async_configure(
        second["flow_id"], {CONF_PORT: MOCK_PORT}
    )
    assert second["type"] is FlowResultType.ABORT
    assert second["reason"] == "already_in_progress"

    await hass.async_block_till_done()
    first = await hass.config_entries.flow.async_configure(first["flow_id"])
    first = await hass.config_entries.flow.async_configure(first["flow_id"], {})
    assert first["type"] is FlowResultType.CREATE_ENTRY


@pytest.mark.usefixtures("mock_bus")
async def test_a_port_added_during_the_title_lookup_is_rejected(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_serial_ports: AsyncMock,
) -> None:
    """Test a flow that finishes while this one names the entry wins the port."""
    result = await _scan(hass)
    assert result["step_id"] == "confirm"

    ports = mock_serial_ports.return_value

    async def _added_meanwhile(hass: HomeAssistant) -> list[AsyncMock]:
        mock_config_entry.add_to_hass(hass)
        return ports

    mock_serial_ports.side_effect = _added_meanwhile
    result = await hass.config_entries.flow.async_configure(result["flow_id"], {})

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


async def test_an_inverter_whose_type_could_not_be_read_is_still_offered(
    hass: HomeAssistant, mock_bus: FakeBus
) -> None:
    """Test a mangled reply still counts as an occupied address."""
    # Truncated cmd `0`: right protocol, too short to parse.
    mock_bus.wake(
        1,
        CannedInverter(
            name="unreadable",
            replies={"0": POWADOR_6400XI.reply_to("0")[:57]},
        ),
    )

    result = await _scan(hass)

    assert result["step_id"] == "confirm"
    assert result["description_placeholders"]["found"].startswith("1, ")


@pytest.mark.usefixtures("mock_bus")
async def test_the_entry_is_named_after_the_port_even_when_unlisted(
    hass: HomeAssistant, mock_serial_ports: AsyncMock
) -> None:
    """Test a port the usb integration does not know falls back to its path."""
    other = AsyncMock()
    other.device = "/dev/ttyUSB9"
    other.description = "something else"
    mock_serial_ports.return_value = [other]

    result = await _scan(hass)
    result = await hass.config_entries.flow.async_configure(result["flow_id"], {})

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == MOCK_PORT


@pytest.mark.usefixtures("mock_bus")
async def test_the_entry_is_named_after_the_port_when_scanning_fails(
    hass: HomeAssistant, mock_serial_ports: AsyncMock
) -> None:
    """Test an unreadable serial-port list does not stop setup."""
    mock_serial_ports.side_effect = OSError("no /dev to read")

    result = await _scan(hass)
    result = await hass.config_entries.flow.async_configure(result["flow_id"], {})

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == MOCK_PORT


async def test_a_local_port_is_stored_by_its_stable_path(
    hass: HomeAssistant, mock_bus: FakeBus
) -> None:
    """Test /dev/ttyUSB0 is resolved to its by-id path before being stored."""
    by_id = "/dev/serial/by-id/usb-Silicon_Labs_CP2102_0001-if00-port0"

    with patch(
        "homeassistant.components.kaco_rs485.config_flow.usb.get_serial_by_id",
        return_value=by_id,
    ) as resolve:
        result = await _scan(hass)
        result = await hass.config_entries.flow.async_configure(result["flow_id"], {})

    resolve.assert_called_once_with(MOCK_PORT)
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"][CONF_PORT] == by_id


@pytest.mark.usefixtures("mock_bus")
async def test_a_proxied_port_is_left_alone(hass: HomeAssistant) -> None:
    """Test an ESPHome proxy URL is not run through by-id resolution."""
    proxy = "esphome-hass://esphome/abc123?port_name=RS-485"

    with patch(
        "homeassistant.components.kaco_rs485.config_flow.usb.get_serial_by_id"
    ) as resolve:
        result = await _scan(hass, proxy)
        result = await hass.config_entries.flow.async_configure(result["flow_id"], {})

    resolve.assert_not_called()
    assert result["data"][CONF_PORT] == proxy


async def test_an_unreadable_by_id_directory_falls_back_to_the_raw_path(
    hass: HomeAssistant, mock_bus: FakeBus
) -> None:
    """Test setup still completes when /dev/serial/by-id cannot be read."""
    with patch(
        "homeassistant.components.kaco_rs485.config_flow.usb.get_serial_by_id",
        side_effect=OSError("permission denied"),
    ):
        result = await _scan(hass)
        result = await hass.config_entries.flow.async_configure(result["flow_id"], {})

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"][CONF_PORT] == MOCK_PORT
