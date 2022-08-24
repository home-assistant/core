"""Test the Airthings BLE config flow."""
from unittest.mock import patch

from airthings_ble import AirthingsDevice
import pytest

from homeassistant.components.airthings_ble.const import DOMAIN
from homeassistant.config_entries import SOURCE_BLUETOOTH, SOURCE_USER
from homeassistant.const import CONF_ADDRESS
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.helpers.update_coordinator import UpdateFailed

from . import (
    UNKNOWN_SERVICE_INFO,
    WAVE_DEVICE_INFO,
    WAVE_SERVICE_INFO,
    patch_airthings_ble,
    patch_async_ble_device_from_address,
    patch_async_setup_entry,
)

from tests.common import MockConfigEntry


async def test_bluetooth_discovery(hass: HomeAssistant):
    """Test discovery via bluetooth with a valid device."""
    with patch_async_ble_device_from_address(WAVE_SERVICE_INFO):
        with patch_airthings_ble(
            AirthingsDevice(name="Airthings Wave+", identifier="CCCCCC")
        ):
            result = await hass.config_entries.flow.async_init(
                DOMAIN,
                context={"source": SOURCE_BLUETOOTH},
                data=WAVE_SERVICE_INFO,
            )

    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "bluetooth_confirm"
    assert result["description_placeholders"] == {"name": "Airthings Wave+ CCCCCC"}

    with patch_async_setup_entry():
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input={"not": "empty"}
        )
    await hass.async_block_till_done()
    assert result["type"] == FlowResultType.CREATE_ENTRY
    assert result["title"] == "Airthings Wave+ CCCCCC"
    assert result["result"].unique_id == "cc:cc:cc:cc:cc:cc"


async def test_bluetooth_discovery_no_BLEDevice(hass: HomeAssistant):
    """Test discovery via bluetooth but there's no BLEDevice."""
    with pytest.raises(UpdateFailed):
        with patch_async_ble_device_from_address(None):
            await hass.config_entries.flow.async_init(
                DOMAIN,
                context={"source": SOURCE_BLUETOOTH},
                data=WAVE_SERVICE_INFO,
            )


async def test_bluetooth_discovery_airthings_ble_update_failed(
    hass: HomeAssistant,
):
    """Test discovery via bluetooth but there's an exception from airthings-ble."""
    with pytest.raises(UpdateFailed):
        with patch_async_ble_device_from_address(WAVE_SERVICE_INFO):
            with patch_airthings_ble(side_effect=UpdateFailed("fail!")):
                await hass.config_entries.flow.async_init(
                    DOMAIN,
                    context={"source": SOURCE_BLUETOOTH},
                    data=WAVE_SERVICE_INFO,
                )


async def test_bluetooth_discovery_unknown_device(hass: HomeAssistant):
    """Test discovery via bluetooth with an invalid device."""

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_BLUETOOTH},
        data=UNKNOWN_SERVICE_INFO,
    )

    assert result["type"] == FlowResultType.ABORT
    assert result["reason"] == "not_supported"


async def test_bluetooth_discovery_already_setup(hass: HomeAssistant):
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


async def test_user_setup(hass: HomeAssistant):
    """Test the user initiated form."""
    with patch(
        "homeassistant.components.airthings_ble.config_flow.async_discovered_service_info",
        return_value=[WAVE_SERVICE_INFO],
    ):
        with patch_async_ble_device_from_address(WAVE_SERVICE_INFO):
            with patch_airthings_ble(
                AirthingsDevice(name="Airthings Wave+", identifier="CCCCCC")
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
        "cc:cc:cc:cc:cc:cc": "cc:cc:cc:cc:cc:cc"
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
    assert result["title"] == "Airthings Wave+ CCCCCC"
    assert result["result"].unique_id == "cc:cc:cc:cc:cc:cc"


async def test_user_setup_no_device(hass: HomeAssistant):
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


async def test_user_setup_existing_and_unknown_device(hass: HomeAssistant):
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
