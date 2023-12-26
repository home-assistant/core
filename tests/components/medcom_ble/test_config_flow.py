"""Test the Medcom Inspector BLE config flow."""
from unittest.mock import patch

from bleak import BleakError
from medcom_ble import MedcomBleDevice

from homeassistant import config_entries
from homeassistant.components.medcom_ble.const import DOMAIN
from homeassistant.const import CONF_ADDRESS
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from . import (
    MEDCOM_DEVICE_INFO,
    MEDCOM_SERVICE_INFO,
    UNKNOWN_SERVICE_INFO,
    patch_async_ble_device_from_address,
    patch_async_setup_entry,
    patch_medcom_ble,
)

from tests.common import MockConfigEntry


async def test_bluetooth_discovery(hass: HomeAssistant) -> None:
    """Test discovery via bluetooth with a valid device."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_BLUETOOTH},
        data=MEDCOM_SERVICE_INFO,
    )

    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "bluetooth_confirm"
    assert result["description_placeholders"] == {"name": "InspectorBLE-D9A0"}

    with patch_async_ble_device_from_address(MEDCOM_SERVICE_INFO), patch_medcom_ble(
        MedcomBleDevice(
            manufacturer="International Medcom",
            model="Inspector BLE",
            model_raw="Inspector-BLE",
            name="Inspector BLE",
            identifier="a0d95a570b00",
        )
    ):
        with patch_async_setup_entry():
            result = await hass.config_entries.flow.async_configure(
                result["flow_id"], user_input={"not": "empty"}
            )
        await hass.async_block_till_done()
        assert result["type"] == FlowResultType.CREATE_ENTRY
        assert result["title"] == "InspectorBLE-D9A0"
        assert result["result"].unique_id == "a0:d9:5a:57:0b:00"


async def test_bluetooth_discovery_already_setup(hass: HomeAssistant) -> None:
    """Test discovery via bluetooth with a valid device when already setup."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id="a0:d9:5a:57:0b:00",
    )
    entry.add_to_hass(hass)
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_BLUETOOTH},
        data=MEDCOM_DEVICE_INFO,
    )
    assert result["type"] == FlowResultType.ABORT
    assert result["reason"] == "already_configured"


async def test_user_setup(hass: HomeAssistant) -> None:
    """Test the user initiated form."""
    with patch(
        "homeassistant.components.medcom_ble.config_flow.async_discovered_service_info",
        return_value=[MEDCOM_SERVICE_INFO],
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )
    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "user"
    assert result["errors"] is None
    assert result["data_schema"] is not None
    schema = result["data_schema"].schema

    assert schema.get(CONF_ADDRESS).container == {
        "a0:d9:5a:57:0b:00": "InspectorBLE-D9A0"
    }

    with patch_async_ble_device_from_address(MEDCOM_SERVICE_INFO), patch_medcom_ble(
        MedcomBleDevice(
            manufacturer="International Medcom",
            model="Inspector BLE",
            model_raw="Inspector-BLE",
            name="Inspector BLE",
            identifier="a0d95a570b00",
        )
    ), patch(
        "homeassistant.components.medcom_ble.async_setup_entry",
        return_value=True,
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input={CONF_ADDRESS: "a0:d9:5a:57:0b:00"}
        )

    await hass.async_block_till_done()
    assert result["type"] == FlowResultType.CREATE_ENTRY
    assert result["title"] == "InspectorBLE-D9A0"
    assert result["result"].unique_id == "a0:d9:5a:57:0b:00"


async def test_user_setup_no_device(hass: HomeAssistant) -> None:
    """Test the user initiated form without any device detected."""
    with patch(
        "homeassistant.components.medcom_ble.config_flow.async_discovered_service_info",
        return_value=[],
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )
    assert result["type"] == FlowResultType.ABORT
    assert result["reason"] == "no_devices_found"


async def test_user_setup_existing_and_unknown_device(hass: HomeAssistant) -> None:
    """Test the user initiated form with existing devices and unknown ones."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id="00:cc:cc:cc:cc:cc",
    )
    entry.add_to_hass(hass)
    with patch(
        "homeassistant.components.medcom_ble.config_flow.async_discovered_service_info",
        return_value=[UNKNOWN_SERVICE_INFO, MEDCOM_SERVICE_INFO],
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )
        assert result["type"] == FlowResultType.FORM
        assert result["step_id"] == "user"
        assert result["errors"] is None
        assert result["data_schema"] is not None

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input={CONF_ADDRESS: "a0:d9:5a:57:0b:00"}
        )

        assert result["type"] == FlowResultType.ABORT
        assert result["reason"] == "cannot_connect"


async def test_user_setup_unknown_device(hass: HomeAssistant) -> None:
    """Test the user initiated form with only unknown devices."""
    with patch(
        "homeassistant.components.medcom_ble.config_flow.async_discovered_service_info",
        return_value=[UNKNOWN_SERVICE_INFO],
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )
        assert result["type"] == FlowResultType.ABORT
        assert result["reason"] == "no_devices_found"


async def test_user_setup_unknown_error(hass: HomeAssistant) -> None:
    """Test the user initiated form with an unknown error."""
    with patch(
        "homeassistant.components.medcom_ble.config_flow.async_discovered_service_info",
        return_value=[MEDCOM_SERVICE_INFO],
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )
    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "user"
    assert result["errors"] is None
    assert result["data_schema"] is not None

    with patch_async_ble_device_from_address(MEDCOM_SERVICE_INFO), patch_medcom_ble(
        None, Exception()
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input={CONF_ADDRESS: "a0:d9:5a:57:0b:00"}
        )

    assert result["type"] == FlowResultType.ABORT
    assert result["reason"] == "unknown"


async def test_user_setup_unable_to_connect(hass: HomeAssistant) -> None:
    """Test the user initiated form with a device that's failing connection."""
    with patch(
        "homeassistant.components.medcom_ble.config_flow.async_discovered_service_info",
        return_value=[MEDCOM_SERVICE_INFO],
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )
    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "user"
    assert result["errors"] is None
    assert result["data_schema"] is not None
    schema = result["data_schema"].schema

    assert schema.get(CONF_ADDRESS).container == {
        "a0:d9:5a:57:0b:00": "InspectorBLE-D9A0"
    }

    with patch_async_ble_device_from_address(MEDCOM_SERVICE_INFO), patch_medcom_ble(
        side_effect=BleakError("An error")
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input={CONF_ADDRESS: "a0:d9:5a:57:0b:00"}
        )

    assert result["type"] == FlowResultType.ABORT
    assert result["reason"] == "cannot_connect"
