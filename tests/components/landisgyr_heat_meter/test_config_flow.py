"""Test the Landis + Gyr Heat Meter config flow."""
from dataclasses import dataclass
from unittest.mock import patch

import serial.tools.list_ports

from homeassistant import config_entries
from homeassistant.components.landisgyr_heat_meter import DOMAIN
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType


def mock_serial_port():
    """Mock of a serial port."""
    port = serial.tools.list_ports_common.ListPortInfo("/dev/ttyUSB1234")
    port.serial_number = "1234"
    port.manufacturer = "Virtual serial port"
    port.device = "/dev/ttyUSB1234"
    port.description = "Some serial port"
    port.pid = 9876
    port.vid = 5678

    return port


@dataclass
class MockUltraheatRead:
    """Mock of the response from the read method of the Ultraheat API."""

    model: str
    device_number: str


@patch(
    "homeassistant.components.landisgyr_heat_meter.config_flow.ultraheat_api.HeatMeterService"
)
async def test_manual_entry(mock_heat_meter, hass: HomeAssistant) -> None:
    """Test manual entry."""

    mock_heat_meter().read.return_value = MockUltraheatRead("LUGCUH50", "123456789")

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "user"
    assert result["errors"] == {}

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"device": "Enter Manually"}
    )

    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "setup_serial_manual_path"
    assert result["errors"] == {}

    with patch(
        "homeassistant.components.landisgyr_heat_meter.async_setup_entry",
        return_value=True,
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {"device": "/dev/ttyUSB0"}
        )

    assert result["type"] == FlowResultType.CREATE_ENTRY
    assert result["title"] == "LUGCUH50"
    assert result["data"] == {
        "device": "/dev/ttyUSB0",
        "model": "LUGCUH50",
        "device_number": "123456789",
    }


@patch(
    "homeassistant.components.landisgyr_heat_meter.config_flow.ultraheat_api.HeatMeterService"
)
@patch("serial.tools.list_ports.comports", return_value=[mock_serial_port()])
async def test_list_entry(mock_port, mock_heat_meter, hass: HomeAssistant) -> None:
    """Test select from list entry."""

    mock_heat_meter().read.return_value = MockUltraheatRead("LUGCUH50", "123456789")
    port = mock_serial_port()

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "user"
    assert result["errors"] == {}

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"device": port.device}
    )
    assert result["type"] == FlowResultType.CREATE_ENTRY
    assert result["title"] == "LUGCUH50"
    assert result["data"] == {
        "device": port.device,
        "model": "LUGCUH50",
        "device_number": "123456789",
    }


@patch(
    "homeassistant.components.landisgyr_heat_meter.config_flow.ultraheat_api.HeatMeterService"
)
async def test_manual_entry_fail(mock_heat_meter, hass: HomeAssistant) -> None:
    """Test manual entry fails."""

    mock_heat_meter().read.side_effect = Exception

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "user"
    assert result["errors"] == {}

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"device": "Enter Manually"}
    )

    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "setup_serial_manual_path"
    assert result["errors"] == {}

    with patch(
        "homeassistant.components.landisgyr_heat_meter.async_setup_entry",
        return_value=True,
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {"device": "/dev/ttyUSB0"}
        )

    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "setup_serial_manual_path"
    assert result["errors"] == {"base": "cannot_connect"}


@patch(
    "homeassistant.components.landisgyr_heat_meter.config_flow.ultraheat_api.HeatMeterService"
)
@patch("serial.tools.list_ports.comports", return_value=[mock_serial_port()])
async def test_list_entry_fail(mock_port, mock_heat_meter, hass: HomeAssistant) -> None:
    """Test select from list entry fails."""

    mock_heat_meter().read.side_effect = Exception
    port = mock_serial_port()

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "user"
    assert result["errors"] == {}

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"device": port.device}
    )
    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "user"
    assert result["errors"] == {"base": "cannot_connect"}
