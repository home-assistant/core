"""Test the Airthings BLE config flow."""
from unittest.mock import patch

from airthings_ble import AirthingsDevice
from bleak import BleakError

from homeassistant.components.airthings_ble.const import DOMAIN
from homeassistant.config_entries import SOURCE_BLUETOOTH, SOURCE_USER
from homeassistant.const import CONF_ADDRESS
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from . import (
    UNKNOWN_SERVICE_INFO,
    WAVE_DEVICE_INFO,
    WAVE_SERVICE_INFO,
    patch_airthings_ble,
    patch_async_ble_device_from_address,
    patch_async_setup_entry,
)

from tests.common import MockConfigEntry


async def test_bluetooth_discovery(hass: HomeAssistant) -> None:
    """Test discovery via bluetooth with a valid device."""
    with patch_async_ble_device_from_address(WAVE_SERVICE_INFO), patch_airthings_ble(
        AirthingsDevice(name="Airthings Wave+", identifier="123456")
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": SOURCE_BLUETOOTH},
            data=WAVE_SERVICE_INFO,
        )

    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "bluetooth_confirm"
    assert result["description_placeholders"] == {"name": "Airthings Wave+ (123456)"}

    with patch_async_setup_entry():
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input={"not": "empty"}
        )
    await hass.async_block_till_done()
    assert result["type"] == FlowResultType.CREATE_ENTRY
    assert result["title"] == "Airthings Wave+ (123456)"
    assert result["result"].unique_id == "cc:cc:cc:cc:cc:cc"


async def test_bluetooth_discovery_no_BLEDevice(hass: HomeAssistant) -> None:
    """Test discovery via bluetooth but there's no BLEDevice."""
    with patch_async_ble_device_from_address(None):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": SOURCE_BLUETOOTH},
            data=WAVE_SERVICE_INFO,
        )
    assert result["type"] == FlowResultType.ABORT
    assert result["reason"] == "cannot_connect"


async def test_bluetooth_discovery_airthings_ble_update_failed(
    hass: HomeAssistant,
) -> None:
    """Test discovery via bluetooth but there's an exception from airthings-ble."""
    for loop in [(Exception(), "unknown"), (BleakError(), "cannot_connect")]:
        exc, reason = loop
        with patch_async_ble_device_from_address(
            WAVE_SERVICE_INFO
        ), patch_airthings_ble(side_effect=exc):
            result = await hass.config_entries.flow.async_init(
                DOMAIN,
                context={"source": SOURCE_BLUETOOTH},
                data=WAVE_SERVICE_INFO,
            )

        assert result["type"] == FlowResultType.ABORT
        assert result["reason"] == reason


async def test_bluetooth_discovery_already_setup(hass: HomeAssistant) -> None:
    """Test discovery via bluetooth with a valid device when already setup."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id="cc:cc:cc:cc:cc:cc",
    )
    entry.add_to_hass(hass)
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_BLUETOOTH},
        data=WAVE_DEVICE_INFO,
    )
    assert result["type"] == FlowResultType.ABORT
    assert result["reason"] == "already_configured"


async def test_user_setup(hass: HomeAssistant) -> None:
    """Test the user initiated form."""
    with patch(
        "homeassistant.components.airthings_ble.config_flow.async_discovered_service_info",
        return_value=[WAVE_SERVICE_INFO],
    ), patch_async_ble_device_from_address(WAVE_SERVICE_INFO), patch_airthings_ble(
        AirthingsDevice(name="Airthings Wave+", identifier="123456")
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": SOURCE_USER}
        )
    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "user"
    assert result["errors"] is None
    assert result["data_schema"] is not None
    schema = result["data_schema"].schema

    assert schema.get(CONF_ADDRESS).container == {
        "cc:cc:cc:cc:cc:cc": "Airthings Wave+ (123456)"
    }

    with patch(
        "homeassistant.components.airthings_ble.async_setup_entry",
        return_value=True,
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input={CONF_ADDRESS: "cc:cc:cc:cc:cc:cc"}
        )

    await hass.async_block_till_done()
    assert result["type"] == FlowResultType.CREATE_ENTRY
    assert result["title"] == "Airthings Wave+ (123456)"
    assert result["result"].unique_id == "cc:cc:cc:cc:cc:cc"


async def test_user_setup_no_device(hass: HomeAssistant) -> None:
    """Test the user initiated form without any device detected."""
    with patch(
        "homeassistant.components.airthings_ble.config_flow.async_discovered_service_info",
        return_value=[],
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": SOURCE_USER}
        )
    assert result["type"] == FlowResultType.ABORT
    assert result["reason"] == "no_devices_found"


async def test_user_setup_existing_and_unknown_device(hass: HomeAssistant) -> None:
    """Test the user initiated form with existing devices and unknown ones."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id="cc:cc:cc:cc:cc:cc",
    )
    entry.add_to_hass(hass)
    with patch(
        "homeassistant.components.airthings_ble.config_flow.async_discovered_service_info",
        return_value=[UNKNOWN_SERVICE_INFO, WAVE_SERVICE_INFO],
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": SOURCE_USER}
        )
    assert result["type"] == FlowResultType.ABORT
    assert result["reason"] == "no_devices_found"


async def test_user_setup_unknown_error(hass: HomeAssistant) -> None:
    """Test the user initiated form with an unknown error."""
    with patch(
        "homeassistant.components.airthings_ble.config_flow.async_discovered_service_info",
        return_value=[WAVE_SERVICE_INFO],
    ), patch_async_ble_device_from_address(WAVE_SERVICE_INFO), patch_airthings_ble(
        None, Exception()
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": SOURCE_USER}
        )

    assert result["type"] == FlowResultType.ABORT
    assert result["reason"] == "unknown"


async def test_user_setup_unable_to_connect(hass: HomeAssistant) -> None:
    """Test the user initiated form with a device that's failing connection."""
    with patch(
        "homeassistant.components.airthings_ble.config_flow.async_discovered_service_info",
        return_value=[WAVE_SERVICE_INFO],
    ), patch_async_ble_device_from_address(WAVE_SERVICE_INFO), patch_airthings_ble(
        side_effect=BleakError("An error")
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": SOURCE_USER}
        )

    assert result["type"] == FlowResultType.ABORT
    assert result["reason"] == "cannot_connect"
