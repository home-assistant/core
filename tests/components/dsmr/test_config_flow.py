"""Test the DSMR config flow."""

from itertools import chain, repeat
from typing import Any
from unittest.mock import DEFAULT, AsyncMock, MagicMock, patch

import pytest
import serial

from homeassistant import config_entries
from homeassistant.components.dsmr.const import DOMAIN
from homeassistant.components.usb import SerialDevice
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from tests.common import MockConfigEntry

SERIAL_DATA = {"serial_id": "12345678", "serial_id_gas": "123456789"}
SERIAL_DATA_SWEDEN = {"serial_id": None, "serial_id_gas": None}


def com_port() -> SerialDevice:
    """Mock of a serial port."""
    return SerialDevice(
        device="/dev/ttyUSB1234",
        serial_number="1234",
        manufacturer="Virtual serial port",
        description="Some serial port",
    )


async def test_setup_network(
    hass: HomeAssistant,
    dsmr_connection_send_validate_fixture: tuple[MagicMock, MagicMock, MagicMock],
) -> None:
    """Test we can setup network."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    assert result["errors"] is None

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {"type": "Network"},
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "setup_network"
    assert result["errors"] == {}

    with patch("homeassistant.components.dsmr.async_setup_entry", return_value=True):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                "host": "10.10.0.1",
                "port": 1234,
                "dsmr_version": "2.2",
            },
        )
        await hass.async_block_till_done()

    entry_data = {
        "host": "10.10.0.1",
        "port": 1234,
        "dsmr_version": "2.2",
        "protocol": "dsmr_protocol",
    }

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "10.10.0.1:1234"
    assert result["data"] == {**entry_data, **SERIAL_DATA}


async def test_setup_network_rfxtrx(
    hass: HomeAssistant,
    dsmr_connection_send_validate_fixture: tuple[MagicMock, MagicMock, MagicMock],
    rfxtrx_dsmr_connection_send_validate_fixture: tuple[
        MagicMock, MagicMock, MagicMock
    ],
) -> None:
    """Test we can setup network."""
    (_connection_factory, _transport, protocol) = dsmr_connection_send_validate_fixture

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    assert result["errors"] is None

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {"type": "Network"},
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "setup_network"
    assert result["errors"] == {}

    # set-up DSMRProtocol to yield no valid telegram, this will retry with RFXtrxDSMRProtocol
    protocol.telegram = {}

    with patch("homeassistant.components.dsmr.async_setup_entry", return_value=True):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                "host": "10.10.0.1",
                "port": 1234,
                "dsmr_version": "2.2",
            },
        )
        await hass.async_block_till_done()

    entry_data = {
        "host": "10.10.0.1",
        "port": 1234,
        "dsmr_version": "2.2",
        "protocol": "rfxtrx_dsmr_protocol",
    }

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "10.10.0.1:1234"
    assert result["data"] == {**entry_data, **SERIAL_DATA}


@pytest.mark.parametrize(
    ("version", "entry_data"),
    [
        (
            "2.2",
            {
                "port": "/dev/ttyUSB1234",
                "dsmr_version": "2.2",
                "protocol": "dsmr_protocol",
                "serial_id": "12345678",
                "serial_id_gas": "123456789",
            },
        ),
        (
            "5B",
            {
                "port": "/dev/ttyUSB1234",
                "dsmr_version": "5B",
                "protocol": "dsmr_protocol",
                "serial_id": "12345678",
                "serial_id_gas": "123456789",
            },
        ),
        (
            "5L",
            {
                "port": "/dev/ttyUSB1234",
                "dsmr_version": "5L",
                "protocol": "dsmr_protocol",
                "serial_id": "12345678",
                "serial_id_gas": "123456789",
            },
        ),
        (
            "5EONHU",
            {
                "port": "/dev/ttyUSB1234",
                "dsmr_version": "5EONHU",
                "protocol": "dsmr_protocol",
                "serial_id": "12345678",
                "serial_id_gas": None,
            },
        ),
        (
            "5S",
            {
                "port": "/dev/ttyUSB1234",
                "dsmr_version": "5S",
                "protocol": "dsmr_protocol",
                "serial_id": None,
                "serial_id_gas": None,
            },
        ),
        (
            "Q3D",
            {
                "port": "/dev/ttyUSB1234",
                "dsmr_version": "Q3D",
                "protocol": "dsmr_protocol",
                "serial_id": "12345678",
                "serial_id_gas": None,
            },
        ),
    ],
)
@patch(
    "homeassistant.components.dsmr.config_flow.usb.async_scan_serial_ports",
    return_value=[com_port()],
)
async def test_setup_serial(
    com_mock,
    hass: HomeAssistant,
    dsmr_connection_send_validate_fixture: tuple[MagicMock, MagicMock, MagicMock],
    version: str,
    entry_data: dict[str, Any],
) -> None:
    """Test we can setup serial."""
    port = com_port()

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    assert result["errors"] is None

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {"type": "Serial"},
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "setup_serial"
    assert result["errors"] == {}

    with patch("homeassistant.components.dsmr.async_setup_entry", return_value=True):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {"port": port.device, "dsmr_version": version},
        )
        await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == port.device
    assert result["data"] == entry_data


@patch(
    "homeassistant.components.dsmr.config_flow.usb.async_scan_serial_ports",
    return_value=[com_port()],
)
async def test_setup_serial_rfxtrx(
    com_mock,
    hass: HomeAssistant,
    dsmr_connection_send_validate_fixture: tuple[MagicMock, MagicMock, MagicMock],
    rfxtrx_dsmr_connection_send_validate_fixture: tuple[
        MagicMock, MagicMock, MagicMock
    ],
) -> None:
    """Test we can setup serial."""
    (_connection_factory, _transport, protocol) = dsmr_connection_send_validate_fixture

    port = com_port()

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    assert result["errors"] is None

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {"type": "Serial"},
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "setup_serial"
    assert result["errors"] == {}

    # set-up DSMRProtocol to yield no valid telegram, this will retry with RFXtrxDSMRProtocol
    protocol.telegram = {}

    with patch("homeassistant.components.dsmr.async_setup_entry", return_value=True):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {"port": port.device, "dsmr_version": "2.2"},
        )
        await hass.async_block_till_done()

    entry_data = {
        "port": port.device,
        "dsmr_version": "2.2",
        "protocol": "rfxtrx_dsmr_protocol",
    }

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == port.device
    assert result["data"] == {**entry_data, **SERIAL_DATA}


@patch(
    "homeassistant.components.dsmr.config_flow.usb.async_scan_serial_ports",
    return_value=[com_port()],
)
async def test_setup_serial_manual(
    com_mock,
    hass: HomeAssistant,
    dsmr_connection_send_validate_fixture: tuple[MagicMock, MagicMock, MagicMock],
) -> None:
    """Test we can setup serial with manual entry."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    assert result["errors"] is None

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {"type": "Serial"},
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "setup_serial"
    assert result["errors"] == {}

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {"port": "Enter Manually", "dsmr_version": "2.2"},
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "setup_serial_manual_path"
    assert result["errors"] is None

    with patch("homeassistant.components.dsmr.async_setup_entry", return_value=True):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {"port": "/dev/ttyUSB0"}
        )
        await hass.async_block_till_done()

    entry_data = {
        "port": "/dev/ttyUSB0",
        "dsmr_version": "2.2",
        "protocol": "dsmr_protocol",
    }

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "/dev/ttyUSB0"
    assert result["data"] == {**entry_data, **SERIAL_DATA}


@patch(
    "homeassistant.components.dsmr.config_flow.usb.async_scan_serial_ports",
    return_value=[com_port()],
)
async def test_setup_serial_fail(
    com_mock,
    hass: HomeAssistant,
    dsmr_connection_send_validate_fixture: tuple[MagicMock, MagicMock, MagicMock],
) -> None:
    """Test failed serial connection."""
    (_connection_factory, transport, protocol) = dsmr_connection_send_validate_fixture

    port = com_port()

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    # override the mock to have it fail the first time and succeed after
    first_fail_connection_factory = AsyncMock(
        return_value=(transport, protocol),
        side_effect=chain([serial.SerialException], repeat(DEFAULT)),
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    assert result["errors"] is None

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {"type": "Serial"},
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "setup_serial"
    assert result["errors"] == {}

    with patch(
        "homeassistant.components.dsmr.config_flow.create_dsmr_reader",
        first_fail_connection_factory,
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {"port": port.device, "dsmr_version": "2.2"},
        )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "setup_serial"
    assert result["errors"] == {"base": "cannot_connect"}


@patch(
    "homeassistant.components.dsmr.config_flow.usb.async_scan_serial_ports",
    return_value=[com_port()],
)
async def test_setup_serial_timeout(
    com_mock,
    hass: HomeAssistant,
    dsmr_connection_send_validate_fixture: tuple[MagicMock, MagicMock, MagicMock],
    rfxtrx_dsmr_connection_send_validate_fixture: tuple[
        MagicMock, MagicMock, MagicMock
    ],
) -> None:
    """Test failed serial connection."""
    (_connection_factory, _transport, protocol) = dsmr_connection_send_validate_fixture
    (
        _connection_factory,
        _transport,
        rfxtrx_protocol,
    ) = rfxtrx_dsmr_connection_send_validate_fixture

    port = com_port()

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    first_timeout_wait_closed = AsyncMock(
        return_value=True,
        side_effect=chain([TimeoutError], repeat(DEFAULT)),
    )
    protocol.wait_closed = first_timeout_wait_closed

    first_timeout_wait_closed = AsyncMock(
        return_value=True,
        side_effect=chain([TimeoutError], repeat(DEFAULT)),
    )
    rfxtrx_protocol.wait_closed = first_timeout_wait_closed

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    assert result["errors"] is None

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {"type": "Serial"},
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "setup_serial"
    assert result["errors"] == {}

    with patch("homeassistant.components.dsmr.async_setup_entry", return_value=True):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {"port": port.device, "dsmr_version": "2.2"}
        )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "setup_serial"
    assert result["errors"] == {"base": "cannot_communicate"}


@patch(
    "homeassistant.components.dsmr.config_flow.usb.async_scan_serial_ports",
    return_value=[com_port()],
)
async def test_setup_serial_wrong_telegram(
    com_mock,
    hass: HomeAssistant,
    dsmr_connection_send_validate_fixture: tuple[MagicMock, MagicMock, MagicMock],
    rfxtrx_dsmr_connection_send_validate_fixture: tuple[
        MagicMock, MagicMock, MagicMock
    ],
) -> None:
    """Test failed telegram data."""
    (_connection_factory, _transport, protocol) = dsmr_connection_send_validate_fixture
    (
        _rfxtrx_connection_factory,
        _transport,
        rfxtrx_protocol,
    ) = rfxtrx_dsmr_connection_send_validate_fixture

    port = com_port()

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    assert result["errors"] is None

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {"type": "Serial"},
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "setup_serial"
    assert result["errors"] == {}

    protocol.telegram = {}
    rfxtrx_protocol.telegram = {}

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {"port": port.device, "dsmr_version": "2.2"},
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "setup_serial"
    assert result["errors"] == {"base": "cannot_communicate"}


async def test_options_flow(hass: HomeAssistant) -> None:
    """Test options flow."""

    entry_data = {
        "port": "/dev/ttyUSB0",
        "dsmr_version": "2.2",
    }

    entry = MockConfigEntry(
        domain=DOMAIN,
        data=entry_data,
        unique_id="/dev/ttyUSB0",
    )
    entry.add_to_hass(hass)

    result = await hass.config_entries.options.async_init(entry.entry_id)

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "init"

    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={
            "time_between_update": 15,
        },
    )

    with (
        patch("homeassistant.components.dsmr.async_setup_entry", return_value=True),
        patch("homeassistant.components.dsmr.async_unload_entry", return_value=True),
    ):
        assert result["type"] is FlowResultType.CREATE_ENTRY

        await hass.async_block_till_done()

    assert entry.options == {"time_between_update": 15}
