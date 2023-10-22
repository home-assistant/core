"""Unit tests for Vevor BLE Heater config flow."""
from unittest.mock import patch

from bleak import BLEDevice
import pytest
from vevor_heater_ble.heater import PowerStatus, VevorDevice, VevorHeaterStatus

from homeassistant import config_entries
from homeassistant.components.vevor_heater.const import DOMAIN
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

pytestmark = pytest.mark.usefixtures("mock_setup_entry")


@pytest.fixture(autouse=True)
def mock_bluetooth(enable_bluetooth):
    """Mock bluetooth for all tests in this module."""


async def test_form_no_device_found(hass: HomeAssistant) -> None:
    """Test that we handle that a device with a given address isn't available."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with patch(
        "homeassistant.components.bluetooth.async_ble_device_from_address",
        return_value=None,
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                "address": "AB:CD:EF:01:23:45",
            },
        )

    assert result2["type"] == FlowResultType.FORM
    assert result2["errors"] == {"base": "cannot_connect"}


async def test_form_cannot_connect(hass: HomeAssistant) -> None:
    """Test we handle if we can't receive an update from the device."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with patch(
        "homeassistant.components.bluetooth.async_ble_device_from_address",
        return_value=BLEDevice(
            address="AB:CD:EF:01:23:45", name="FooBar", details=None, rssi=-1
        ),
    ), patch(
        "vevor_heater_ble.heater.VevorDevice.refresh_status",
        autospec=True,
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                "address": "AB:CD:EF:01:23:45",
            },
        )

    assert result2["type"] == FlowResultType.FORM
    assert result2["errors"] == {"base": "cannot_connect"}


async def test_form_ok(hass: HomeAssistant) -> None:
    """Test we successfully create the device if available."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with patch(
        "homeassistant.components.bluetooth.async_ble_device_from_address",
        return_value=BLEDevice(
            address="AB:CD:EF:01:23:45", name="FooBar", details=None, rssi=-1
        ),
    ):

        def update_self_status(self, bledevice):
            self.status = VevorHeaterStatus(power_status=PowerStatus.OFF)

        with patch.object(
            VevorDevice, "refresh_status", autospec=True
        ) as refresh_status:
            refresh_status.side_effect = update_self_status
            result2 = await hass.config_entries.flow.async_configure(
                result["flow_id"],
                {
                    "address": "AB:CD:EF:01:23:45",
                },
            )

    assert result2["type"] == FlowResultType.CREATE_ENTRY
    assert "errors" not in result2
    assert result2["title"] == "Vevor FooBar"


async def test_form_ok_without_name(hass: HomeAssistant) -> None:
    """Test we successfully create the device if it doesn't have a name."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with patch(
        "homeassistant.components.bluetooth.async_ble_device_from_address",
        return_value=BLEDevice(
            address="AB:CD:EF:01:23:45", name=None, details=None, rssi=-1
        ),
    ):

        def update_self_status(self, bledevice):
            self.status = VevorHeaterStatus(power_status=PowerStatus.OFF)

        with patch.object(
            VevorDevice, "refresh_status", autospec=True
        ) as refresh_status:
            refresh_status.side_effect = update_self_status
            result2 = await hass.config_entries.flow.async_configure(
                result["flow_id"],
                {
                    "address": "AB:CD:EF:01:23:45",
                },
            )

    assert result2["type"] == FlowResultType.CREATE_ENTRY
    assert "errors" not in result2
    assert result2["title"] == "Vevor AB:CD:EF:01:23:45"
