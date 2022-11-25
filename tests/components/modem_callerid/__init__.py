"""Tests for the Modem Caller ID integration."""

from unittest.mock import patch

from phone_modem import DEFAULT_PORT

from homeassistant.components.usb import USBDevice


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


def serial_port():
    """Mock of a serial port."""
    return USBDevice(
        device=DEFAULT_PORT,
        vid=None,
        pid=None,
        serial_number="1234",
        manufacturer="Virtual serial port",
        description="Some serial port",
    )
