"""Test the Aurora ABB PowerOne Solar PV config flow."""

from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from serial.tools import list_ports_common

from homeassistant import config_entries, setup
from homeassistant.components.aurora_abb_powerone.aurora_client import AuroraClientError
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
    INVERTER_SERIAL_ADDRESS_DEFAULT,
    TRANSPORT_SERIAL,
    TRANSPORT_TCP,
)
from homeassistant.const import ATTR_SERIAL_NUMBER
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType


async def test_serial_flow_success(hass: HomeAssistant) -> None:
    """Test serial flow successful configuration."""
    await setup.async_setup_component(hass, DOMAIN, {})

    fakecomports = [list_ports_common.ListPortInfo("/dev/ttyUSB7")]

    with patch("serial.tools.list_ports.comports", return_value=fakecomports):
        choose_transport_result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )
        assert choose_transport_result["type"] is FlowResultType.FORM
        assert choose_transport_result["step_id"] == "choose_transport"

        configure_serial_result = await hass.config_entries.flow.async_configure(
            choose_transport_result["flow_id"], {CONF_TRANSPORT: TRANSPORT_SERIAL}
        )
        assert configure_serial_result["type"] is FlowResultType.FORM
        assert configure_serial_result["step_id"] == "configure_serial"

        client = MagicMock()
        client.try_connect_and_fetch_identifier.return_value = SimpleNamespace(
            serial_number="9876543",
            model="9.8.7.6 (A.B.C)",
            firmware="1.234",
        )

        with (
            patch(
                "homeassistant.components.aurora_abb_powerone.config_flow.AuroraClient.from_serial",
                return_value=client,
            ),
            patch(
                "homeassistant.components.aurora_abb_powerone.async_setup_entry",
                return_value=True,
            ) as mock_setup_entry,
        ):
            create_entry_result = await hass.config_entries.flow.async_configure(
                configure_serial_result["flow_id"],
                {
                    CONF_SERIAL_COMPORT: "/dev/ttyUSB7",
                    CONF_INVERTER_SERIAL_ADDRESS: 2,
                },
            )

    assert create_entry_result["type"] is FlowResultType.CREATE_ENTRY
    assert create_entry_result["data"] == {
        CONF_SERIAL_COMPORT: "/dev/ttyUSB7",
        CONF_INVERTER_SERIAL_ADDRESS: 2,
        CONF_TRANSPORT: TRANSPORT_SERIAL,
        ATTR_SERIAL_NUMBER: "9876543",
        ATTR_MODEL: "9.8.7.6 (A.B.C)",
        ATTR_FIRMWARE: "1.234",
        "title": DEFAULT_INTEGRATION_TITLE,
    }
    await hass.async_block_till_done()
    assert len(mock_setup_entry.mock_calls) == 1


async def test_serial_no_comports(hass: HomeAssistant) -> None:
    """Test abort when no serial ports are found."""

    with patch("serial.tools.list_ports.comports", return_value=[]):
        choose_transport_result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )

    assert choose_transport_result["type"] is FlowResultType.FORM
    assert choose_transport_result["step_id"] == "choose_transport"

    configure_serial_result = await hass.config_entries.flow.async_configure(
        choose_transport_result["flow_id"], {CONF_TRANSPORT: TRANSPORT_SERIAL}
    )
    assert configure_serial_result["type"] is FlowResultType.ABORT
    assert configure_serial_result["reason"] == "no_serial_ports"


async def test_serial_error_paths(hass: HomeAssistant) -> None:
    """Test faulty serial flow."""
    fakecomports = [list_ports_common.ListPortInfo("/dev/ttyUSB7")]

    with patch("serial.tools.list_ports.comports", return_value=fakecomports):
        choose_transport_result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )
        assert choose_transport_result["type"] is FlowResultType.FORM
        assert choose_transport_result["step_id"] == "choose_transport"

        configure_serial_result = await hass.config_entries.flow.async_configure(
            choose_transport_result["flow_id"], {CONF_TRANSPORT: TRANSPORT_SERIAL}
        )
        assert configure_serial_result["type"] is FlowResultType.FORM
        assert configure_serial_result["step_id"] == "configure_serial"

        client = MagicMock()
        client.try_connect_and_fetch_identifier.side_effect = OSError(
            19, "no such device"
        )
        with patch(
            "homeassistant.components.aurora_abb_powerone.config_flow.AuroraClient.from_serial",
            return_value=client,
        ):
            form_result_invalid_port = await hass.config_entries.flow.async_configure(
                configure_serial_result["flow_id"],
                {
                    CONF_SERIAL_COMPORT: "/dev/ttyUSB7",
                    CONF_INVERTER_SERIAL_ADDRESS: INVERTER_SERIAL_ADDRESS_DEFAULT,
                },
            )
        assert form_result_invalid_port["type"] is FlowResultType.FORM
        assert form_result_invalid_port["errors"] == {"base": "invalid_serial_port"}

        client = MagicMock()
        client.try_connect_and_fetch_identifier.side_effect = AuroraClientError(
            "could not open port /dev/ttyUSB7"
        )
        with patch(
            "homeassistant.components.aurora_abb_powerone.config_flow.AuroraClient.from_serial",
            return_value=client,
        ):
            form_result_faulty_port = await hass.config_entries.flow.async_configure(
                choose_transport_result["flow_id"],
                {
                    CONF_SERIAL_COMPORT: "/dev/ttyUSB7",
                    CONF_INVERTER_SERIAL_ADDRESS: INVERTER_SERIAL_ADDRESS_DEFAULT,
                },
            )
        assert form_result_faulty_port["type"] is FlowResultType.FORM
        assert form_result_faulty_port["errors"] == {"base": "cannot_open_serial_port"}

        client = MagicMock()
        client.try_connect_and_fetch_identifier.side_effect = AuroraClientError(
            "No response after 5 seconds"
        )
        with patch(
            "homeassistant.components.aurora_abb_powerone.config_flow.AuroraClient.from_serial",
            return_value=client,
        ):
            form_result_cannot_connect = await hass.config_entries.flow.async_configure(
                choose_transport_result["flow_id"],
                {
                    CONF_SERIAL_COMPORT: "/dev/ttyUSB7",
                    CONF_INVERTER_SERIAL_ADDRESS: INVERTER_SERIAL_ADDRESS_DEFAULT,
                },
            )
        assert form_result_cannot_connect["type"] is FlowResultType.FORM
        assert form_result_cannot_connect["errors"] == {"base": "cannot_connect"}

        client = MagicMock()
        client.try_connect_and_fetch_identifier.side_effect = AuroraClientError(
            "Some other message!!!123"
        )
        with patch(
            "homeassistant.components.aurora_abb_powerone.config_flow.AuroraClient.from_serial",
            return_value=client,
        ):
            res4 = await hass.config_entries.flow.async_configure(
                choose_transport_result["flow_id"],
                {
                    CONF_SERIAL_COMPORT: "/dev/ttyUSB7",
                    CONF_INVERTER_SERIAL_ADDRESS: INVERTER_SERIAL_ADDRESS_DEFAULT,
                },
            )
        assert res4["type"] is FlowResultType.FORM
        assert res4["errors"] == {"base": "cannot_connect"}


async def test_tcp_flow_success(hass: HomeAssistant) -> None:
    """Test successful TCP config via choose_transport -> configure_tcp."""
    await setup.async_setup_component(hass, DOMAIN, {})

    choose_transport_result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert choose_transport_result["type"] is FlowResultType.FORM
    assert choose_transport_result["step_id"] == "choose_transport"

    configure_tcp_result = await hass.config_entries.flow.async_configure(
        choose_transport_result["flow_id"], {CONF_TRANSPORT: TRANSPORT_TCP}
    )
    assert configure_tcp_result["type"] is FlowResultType.FORM
    assert configure_tcp_result["step_id"] == "configure_tcp"

    client = MagicMock()
    client.try_connect_and_fetch_identifier.return_value = SimpleNamespace(
        serial_number="TCP-123456",
        model="M1.2.3 (XYZ)",
        firmware="2.0.0",
    )

    with (
        patch(
            "homeassistant.components.aurora_abb_powerone.config_flow.AuroraClient.from_tcp",
            return_value=client,
        ),
        patch(
            "homeassistant.components.aurora_abb_powerone.async_setup_entry",
            return_value=True,
        ) as mock_setup_entry,
    ):
        create_entry_result = await hass.config_entries.flow.async_configure(
            configure_tcp_result["flow_id"],
            {
                CONF_TCP_HOST: "127.0.0.1",
                CONF_TCP_PORT: 502,
                CONF_INVERTER_SERIAL_ADDRESS: 2,
            },
        )

    assert create_entry_result["type"] is FlowResultType.CREATE_ENTRY
    assert create_entry_result["title"] == DEFAULT_INTEGRATION_TITLE
    assert create_entry_result["data"] == {
        CONF_TCP_HOST: "127.0.0.1",
        CONF_TCP_PORT: 502,
        CONF_INVERTER_SERIAL_ADDRESS: 2,
        CONF_TRANSPORT: TRANSPORT_TCP,
        ATTR_SERIAL_NUMBER: "TCP-123456",
        ATTR_MODEL: "M1.2.3 (XYZ)",
        ATTR_FIRMWARE: "2.0.0",
        "title": DEFAULT_INTEGRATION_TITLE,
    }
    await hass.async_block_till_done()
    assert len(mock_setup_entry.mock_calls) == 1


async def test_tcp_error_cannot_connect(hass: HomeAssistant) -> None:
    """Test TCP path error handling -> cannot_connect."""
    choose_transport_result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert choose_transport_result["type"] is FlowResultType.FORM
    assert choose_transport_result["step_id"] == "choose_transport"

    configure_tcp_result = await hass.config_entries.flow.async_configure(
        choose_transport_result["flow_id"], {CONF_TRANSPORT: TRANSPORT_TCP}
    )
    assert configure_tcp_result["type"] is FlowResultType.FORM
    assert configure_tcp_result["step_id"] == "configure_tcp"

    client = MagicMock()
    client.try_connect_and_fetch_identifier.side_effect = AuroraClientError(
        "some tcp error"
    )

    with patch(
        "homeassistant.components.aurora_abb_powerone.config_flow.AuroraClient.from_tcp",
        return_value=client,
    ):
        form_result = await hass.config_entries.flow.async_configure(
            configure_tcp_result["flow_id"],
            {
                CONF_TCP_HOST: "192.0.2.10",
                CONF_TCP_PORT: 8899,
                CONF_INVERTER_SERIAL_ADDRESS: INVERTER_SERIAL_ADDRESS_DEFAULT,
            },
        )

    assert form_result["type"] is FlowResultType.FORM
    assert form_result["step_id"] == "configure_tcp"
    assert form_result["errors"] == {"base": "cannot_connect"}
