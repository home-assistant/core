"""Tests for the Modem Caller ID integration."""

from unittest.mock import patch

from phone_modem import DEFAULT_PORT
from serial.tools.list_ports_common import ListPortInfo


def patch_init_modem():
    """Mock modem."""
    return patch(
        "homeassistant.components.modem_callerid.PhoneModem.initialize",
    )


def patch_config_flow_modem():
    """Mock modem config flow."""
    return patch(
        "homeassistant.components.modem_callerid.config_flow.PhoneModem.test",
    )


def com_port():
    """Mock of a serial port."""
    port = ListPortInfo(DEFAULT_PORT)
    port.serial_number = "1234"
    port.manufacturer = "Virtual serial port"
    port.device = DEFAULT_PORT
    port.description = "Some serial port"

    return port
