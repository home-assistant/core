"""Unit tests for Vevor BLE Heater config flow."""
from unittest.mock import patch

from home_assistant_bluetooth import BluetoothServiceInfo
import pytest

from homeassistant import config_entries
from homeassistant.components.vevor_heater.config_flow import CannotConnect
from homeassistant.components.vevor_heater.const import DOMAIN
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

pytestmark = pytest.mark.usefixtures("mock_setup_entry")


@pytest.fixture(autouse=True)
def mock_bluetooth(enable_bluetooth):
    """Mock bluetooth for all tests in this module."""


async def test_form_cannot_connect(hass: HomeAssistant) -> None:
    """Test we successfully create the device if we can't connect to it."""

    with patch(
        "homeassistant.components.vevor_heater.config_flow.validate_device",
        side_effect=CannotConnect,
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_BLUETOOTH},
            data=BluetoothServiceInfo(
                name="BYD-12345678",
                address="01:03:05:07:09:11",
                rssi=-1,
                manufacturer_data={33465: b""},
                service_data={},
                service_uuids=["0000ffe0-0000-1000-8000-00805f9b34fb"],
                source="local",
            ),
        )

        assert result["type"] == FlowResultType.ABORT
        assert result["reason"] == "not_supported"


async def test_form_ok_wit_name(hass: HomeAssistant) -> None:
    """Test we successfully create the device if it has a name."""

    with patch(
        "homeassistant.components.vevor_heater.config_flow.validate_device",
        return_value={"title": "Vevor TestTestTest"},
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_BLUETOOTH},
            data=BluetoothServiceInfo(
                name="BYD-12345678",
                address="01:03:05:07:09:11",
                rssi=-1,
                manufacturer_data={33465: b""},
                service_data={},
                service_uuids=["0000ffe0-0000-1000-8000-00805f9b34fb"],
                source="local",
            ),
        )

        assert result["type"] == FlowResultType.FORM
        assert result["step_id"] == "bluetooth_confirm"

        with patch(
            "homeassistant.components.vevor_heater.async_setup_entry", return_value=True
        ):
            result2 = await hass.config_entries.flow.async_configure(
                result["flow_id"], user_input={}
            )
        assert result2["type"] == FlowResultType.CREATE_ENTRY
        assert result2["title"] == "Vevor BYD-12345678"
        assert result2["result"].unique_id == "01:03:05:07:09:11"


async def test_form_ok_without_name(hass: HomeAssistant) -> None:
    """Test we successfully create the device if it doesn't have a name."""

    with patch(
        "homeassistant.components.vevor_heater.config_flow.validate_device",
        return_value={"title": "Vevor TestTestTest"},
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_BLUETOOTH},
            data=BluetoothServiceInfo(
                name=None,
                address="01:03:05:07:09:11",
                rssi=-1,
                manufacturer_data={33465: b""},
                service_data={},
                service_uuids=["0000ffe0-0000-1000-8000-00805f9b34fb"],
                source="local",
            ),
        )

        assert result["type"] == FlowResultType.FORM
        assert result["step_id"] == "bluetooth_confirm"

        with patch(
            "homeassistant.components.vevor_heater.async_setup_entry", return_value=True
        ):
            result2 = await hass.config_entries.flow.async_configure(
                result["flow_id"], user_input={}
            )
        assert result2["type"] == FlowResultType.CREATE_ENTRY
        assert result2["title"] == "Vevor 01:03:05:07:09:11"
        assert result2["result"].unique_id == "01:03:05:07:09:11"
