"""Test the Landis + Gyr Heat Meter config flow."""

from dataclasses import dataclass
from unittest.mock import patch

import pytest
import serialx

from homeassistant import config_entries
from homeassistant.components.landisgyr_heat_meter import DOMAIN
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from tests.common import MockConfigEntry

API_HEAT_METER_SERVICE = (
    "homeassistant.components.landisgyr_heat_meter"
    ".config_flow.ultraheat_api.HeatMeterService"
)

pytestmark = pytest.mark.usefixtures("mock_setup_entry")


@dataclass
class MockUltraheatRead:
    """Mock of the response from the read method of the Ultraheat API."""

    model: str
    device_number: str


@patch(API_HEAT_METER_SERVICE)
async def test_user_flow_success(mock_heat_meter, hass: HomeAssistant) -> None:
    """Test successful user flow."""

    mock_heat_meter().read.return_value = MockUltraheatRead("LUGCUH50", "123456789")

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    assert result["errors"] == {}

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"device": "/dev/ttyUSB0"}
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "LUGCUH50"
    assert result["data"] == {
        "device": "/dev/ttyUSB0",
        "model": "LUGCUH50",
        "device_number": "123456789",
    }


@patch(API_HEAT_METER_SERVICE)
async def test_user_flow_cannot_connect_oserror(
    mock_heat_meter, hass: HomeAssistant
) -> None:
    """Test connection failure due to OSError."""

    mock_heat_meter().read.side_effect = OSError("device unavailable")

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    assert result["errors"] == {}

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"device": "/dev/ttyUSB0"}
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    assert result["errors"] == {"base": "cannot_connect"}


@patch(API_HEAT_METER_SERVICE)
async def test_user_flow_cannot_connect_serial_exception(
    mock_heat_meter, hass: HomeAssistant
) -> None:
    """Test connection failure due to serialx.SerialException."""

    mock_heat_meter().read.side_effect = serialx.SerialException("connection failed")

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    assert result["errors"] == {}

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"device": "/dev/ttyUSB0"}
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    assert result["errors"] == {"base": "cannot_connect"}


@patch(API_HEAT_METER_SERVICE)
async def test_already_configured(mock_heat_meter, hass: HomeAssistant) -> None:
    """Test we abort if the Heat Meter is already configured."""

    entry_data = {
        "device": "/dev/USB0",
        "model": "LUGCUH50",
        "device_number": "123456789",
    }
    mock_entry = MockConfigEntry(domain=DOMAIN, unique_id="123456789", data=entry_data)
    mock_entry.add_to_hass(hass)

    await hass.config_entries.async_setup(mock_entry.entry_id)
    await hass.async_block_till_done()

    mock_heat_meter().read.return_value = MockUltraheatRead("LUGCUH50", "123456789")

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"device": "/dev/ttyUSB0"}
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"
