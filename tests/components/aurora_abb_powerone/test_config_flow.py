"""Test the Aurora ABB PowerOne Solar PV config flow (serial + TCP)."""

from unittest.mock import patch

from aurorapy.client import AuroraError, AuroraTimeoutError
from serial.tools import list_ports_common

from homeassistant import config_entries, setup
from homeassistant.components.aurora_abb_powerone.const import (
    ATTR_FIRMWARE,
    ATTR_MODEL,
    CONF_INVERTER_SERIAL_ADDRESS,
    CONF_SERIAL_COMPORT,
    CONF_TCP_HOST,
    CONF_TCP_PORT,
    CONF_TRANSPORT,
    DEFAULT_INTEGRATION_TITLE,
    DOMAIN,
    TCP_PORT_DEFAULT,
    TRANSPORT_SERIAL,
    TRANSPORT_TCP,
)
from homeassistant.const import ATTR_SERIAL_NUMBER
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType


async def _start_user_flow(hass: HomeAssistant) -> dict:
    """Start the user flow and return initial form result."""
    await setup.async_setup_component(hass, DOMAIN, {})
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {}
    return result


async def test_serial_happy_path(hass: HomeAssistant) -> None:
    """Test serial config happy path with transport selection."""

    # Initial user step (transport choice)
    user_step = await _start_user_flow(hass)

    # Choose SERIAL -> moves to serial step (which scans com ports)
    fakecomports = [list_ports_common.ListPortInfo("/dev/ttyUSB7")]
    with patch("serial.tools.list_ports.comports", return_value=fakecomports):
        serial_step = await hass.config_entries.flow.async_configure(
            user_step["flow_id"], {CONF_TRANSPORT: TRANSPORT_SERIAL}
        )

    assert serial_step["type"] is FlowResultType.FORM
    assert serial_step["step_id"] == "configure_serial"

    with (
        patch("aurorapy.client.AuroraSerialClient.connect", return_value=None),
        patch(
            "aurorapy.client.AuroraSerialClient.serial_number", return_value="9876543"
        ),
        patch("aurorapy.client.AuroraSerialClient.version", return_value="9.8.7.6"),
        patch("aurorapy.client.AuroraSerialClient.pn", return_value="A.B.C"),
        patch(
            "aurorapy.client.AuroraSerialClient.firmware", return_value="1.234"
        ) as mock_setup,
        patch(
            "homeassistant.components.aurora_abb_powerone.async_setup_entry",
            return_value=True,
        ) as mock_setup_entry,
    ):
        result = await hass.config_entries.flow.async_configure(
            serial_step["flow_id"],
            {CONF_SERIAL_COMPORT: "/dev/ttyUSB7", CONF_INVERTER_SERIAL_ADDRESS: 7},
        )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"] == {
        CONF_SERIAL_COMPORT: "/dev/ttyUSB7",
        CONF_INVERTER_SERIAL_ADDRESS: 7,
        ATTR_FIRMWARE: "1.234",
        ATTR_MODEL: "9.8.7.6 (A.B.C)",
        ATTR_SERIAL_NUMBER: "9876543",
        "title": DEFAULT_INTEGRATION_TITLE,
        CONF_TRANSPORT: TRANSPORT_SERIAL,
    }
    await hass.async_block_till_done()
    assert len(mock_setup.mock_calls) == 1
    assert len(mock_setup_entry.mock_calls) == 1


async def test_serial_no_comports(hass: HomeAssistant) -> None:
    """Test we abort when there are no serial ports."""

    user_step = await _start_user_flow(hass)

    with patch("serial.tools.list_ports.comports", return_value=[]):
        result = await hass.config_entries.flow.async_configure(
            user_step["flow_id"], {CONF_TRANSPORT: TRANSPORT_SERIAL}
        )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "no_serial_ports"


async def test_serial_invalid_com_ports(hass: HomeAssistant) -> None:
    """Test error handling for invalid serial port scenarios."""

    user_step = await _start_user_flow(hass)

    fakecomports = [list_ports_common.ListPortInfo("/dev/ttyUSB7")]
    with patch("serial.tools.list_ports.comports", return_value=fakecomports):
        serial_step = await hass.config_entries.flow.async_configure(
            user_step["flow_id"], {CONF_TRANSPORT: TRANSPORT_SERIAL}
        )

    # OSError errno 19 -> invalid_serial_port
    with patch(
        "aurorapy.client.AuroraSerialClient.connect",
        side_effect=OSError(19, "...no such device..."),
        return_value=None,
    ):
        result = await hass.config_entries.flow.async_configure(
            serial_step["flow_id"],
            {CONF_SERIAL_COMPORT: "/dev/ttyUSB7", CONF_INVERTER_SERIAL_ADDRESS: 7},
        )
    assert result["errors"] == {"base": "invalid_serial_port"}

    # AuroraError 'could not open port' -> cannot_open_serial_port
    with patch(
        "aurorapy.client.AuroraSerialClient.connect",
        side_effect=AuroraError("..could not open port..."),
        return_value=None,
    ):
        result = await hass.config_entries.flow.async_configure(
            serial_step["flow_id"],
            {CONF_SERIAL_COMPORT: "/dev/ttyUSB7", CONF_INVERTER_SERIAL_ADDRESS: 7},
        )
    assert result["errors"] == {"base": "cannot_open_serial_port"}

    # AuroraTimeoutError 'No response after' -> cannot_connect
    with patch(
        "aurorapy.client.AuroraSerialClient.connect",
        side_effect=AuroraTimeoutError("...No response after..."),
        return_value=None,
    ):
        result = await hass.config_entries.flow.async_configure(
            serial_step["flow_id"],
            {CONF_SERIAL_COMPORT: "/dev/ttyUSB7", CONF_INVERTER_SERIAL_ADDRESS: 7},
        )
    assert result["errors"] == {"base": "cannot_connect"}

    # Generic AuroraError -> cannot_connect, client.close called once
    with (
        patch(
            "aurorapy.client.AuroraSerialClient.connect",
            side_effect=AuroraError("...Some other message!!!123..."),
            return_value=None,
        ),
        patch("serial.Serial.isOpen", return_value=True),
        patch("aurorapy.client.AuroraSerialClient.close") as mock_clientclose,
    ):
        result = await hass.config_entries.flow.async_configure(
            serial_step["flow_id"],
            {CONF_SERIAL_COMPORT: "/dev/ttyUSB7", CONF_INVERTER_SERIAL_ADDRESS: 7},
        )
    assert result["errors"] == {"base": "cannot_connect"}
    assert len(mock_clientclose.mock_calls) == 1


async def test_tcp_happy_path(hass: HomeAssistant) -> None:
    """Test TCP config happy path with transport selection."""

    user_step = await _start_user_flow(hass)

    # Choose TCP -> goes to configure_tcp step
    tcp_step = await hass.config_entries.flow.async_configure(
        user_step["flow_id"], {CONF_TRANSPORT: TRANSPORT_TCP}
    )
    assert tcp_step["type"] is FlowResultType.FORM
    assert tcp_step["step_id"] == "configure_tcp"

    with (
        patch("aurorapy.client.AuroraTCPClient.connect", return_value=None),
        patch("aurorapy.client.AuroraTCPClient.serial_number", return_value="1112223"),
        patch("aurorapy.client.AuroraTCPClient.version", return_value="1.2.3.4"),
        patch("aurorapy.client.AuroraTCPClient.pn", return_value="X.Y.Z"),
        patch("aurorapy.client.AuroraTCPClient.firmware", return_value="0.999"),
        patch(
            "homeassistant.components.aurora_abb_powerone.async_setup_entry",
            return_value=True,
        ) as mock_setup_entry,
    ):
        result = await hass.config_entries.flow.async_configure(
            tcp_step["flow_id"],
            {
                CONF_TCP_HOST: "192.168.1.10",
                CONF_TCP_PORT: TCP_PORT_DEFAULT,
                CONF_INVERTER_SERIAL_ADDRESS: 5,
            },
        )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"] == {
        CONF_TCP_HOST: "192.168.1.10",
        CONF_TCP_PORT: TCP_PORT_DEFAULT,
        CONF_INVERTER_SERIAL_ADDRESS: 5,
        ATTR_FIRMWARE: "0.999",
        ATTR_MODEL: "1.2.3.4 (X.Y.Z)",
        ATTR_SERIAL_NUMBER: "1112223",
        "title": DEFAULT_INTEGRATION_TITLE,
        CONF_TRANSPORT: TRANSPORT_TCP,
    }
    await hass.async_block_till_done()
    assert len(mock_setup_entry.mock_calls) == 1


async def test_tcp_cannot_connect(hass: HomeAssistant) -> None:
    """Test TCP config error handling -> cannot_connect on AuroraError."""

    user_step = await _start_user_flow(hass)

    tcp_step = await hass.config_entries.flow.async_configure(
        user_step["flow_id"], {CONF_TRANSPORT: TRANSPORT_TCP}
    )
    assert tcp_step["type"] is FlowResultType.FORM
    assert tcp_step["step_id"] == "configure_tcp"

    with patch(
        "aurorapy.client.AuroraTCPClient.connect",
        side_effect=AuroraError("Some TCP issue"),
        return_value=None,
    ):
        result = await hass.config_entries.flow.async_configure(
            tcp_step["flow_id"],
            {
                CONF_TCP_HOST: "192.168.1.10",
                CONF_TCP_PORT: TCP_PORT_DEFAULT,
                CONF_INVERTER_SERIAL_ADDRESS: 3,
            },
        )

    assert result["errors"] == {"base": "cannot_connect"}
