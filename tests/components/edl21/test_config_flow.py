"""Tests for the EDL21 config flow."""
from homeassistant import config_entries, data_entry_flow
from homeassistant.components.edl21.sensor import DOMAIN, CONF_SERIAL_PORT
from homeassistant.components.edl21.config_flow import CONF_MANUAL_PATH
from homeassistant.components.hassio import HassioServiceInfo
from homeassistant.config_entries import SOURCE_USER
from homeassistant.const import CONF_NAME
from homeassistant.core import HomeAssistant
import homeassistant.components.edl21
from homeassistant.const import CONF_SOURCE

from unittest.mock import AsyncMock, MagicMock, patch, sentinel

from tests.common import MockConfigEntry

import pytest
import serial.tools.list_ports


def com_port():
    """Mock of a serial port."""
    port = serial.tools.list_ports_common.ListPortInfo("/dev/ttyUSB1234")
    port.serial_number = "1234"
    port.manufacturer = "Virtual serial port"
    port.device = "/dev/ttyUSB1"
    port.description = "Some serial port"

    return port


@patch("serial.tools.list_ports.comports", MagicMock(return_value=[]))
async def test_no_port_config_form(hass: HomeAssistant) -> None:
    """Test that the setup form is served."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={CONF_SOURCE: SOURCE_USER}
    )

    assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
    assert result["step_id"] == "pick_manual"


async def test_with_data(hass: HomeAssistant) -> None:
    """Test that entry creation."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={CONF_SOURCE: SOURCE_USER},
        data={CONF_SERIAL_PORT: "/dev/ttyTEST", CONF_NAME: "TEST"},
    )

    assert result["type"] == data_entry_flow.RESULT_TYPE_CREATE_ENTRY
    assert result["data"][CONF_NAME] == "TEST"
    assert result["data"][CONF_SERIAL_PORT] == "/dev/ttyTEST"


@patch("serial.tools.list_ports.comports", MagicMock(return_value=[com_port()]))
async def test_user_flow_ports(hass: HomeAssistant):
    """Test user flow -- radio detected."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={CONF_SOURCE: SOURCE_USER}
    )
    assert result["type"] == data_entry_flow.RESULT_TYPE_FORM


async def test_with_manual(hass: HomeAssistant) -> None:
    """Test that entry creation."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={CONF_SOURCE: SOURCE_USER},
        data={CONF_SERIAL_PORT: CONF_MANUAL_PATH, CONF_NAME: "TEST"},
    )

    assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
    assert result["step_id"] == "pick_manual"


async def test_with_data_manual(hass: HomeAssistant) -> None:
    """Test that entry creation."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={CONF_SOURCE: "pick_manual"},
        data={CONF_SERIAL_PORT: "/dev/ttyTEST", CONF_NAME: "TEST"},
    )

    assert result["type"] == data_entry_flow.RESULT_TYPE_CREATE_ENTRY
    assert result["data"][CONF_NAME] == "TEST"
    assert result["data"][CONF_SERIAL_PORT] == "/dev/ttyTEST"
