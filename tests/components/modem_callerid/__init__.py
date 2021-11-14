"""Tests for the Modem Caller ID integration."""

from unittest.mock import patch

from phone_modem import DEFAULT_PORT
import serial.tools.list_ports_common


def patch_init_modem():
    """Mock modem."""
    return patch(
        "homeassistant.components.modem_callerid.PhoneModem.initialize",
        autospec=True,
    )


def patch_config_flow_modem(mocked_modem):
    """Mock modem config flow."""
    return patch(
        "homeassistant.components.modem_callerid.config_flow.PhoneModem.test",
        autospec=True,
        return_value=mocked_modem,
    )


def com_port():
    """Mock of a serial port."""
    port = serial.tools.list_ports_common.ListPortInfo(DEFAULT_PORT)
    port.serial_number = "1234"
    port.manufacturer = "Virtual serial port"
    port.device = DEFAULT_PORT
    port.description = "Some serial port"

    return port
