"""Tests for the Tuya config flow."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.sensor import SensorDeviceClass
from homeassistant.components.tuya.const import (
    CONF_APP_TYPE,
    CONF_USER_CODE,
    DOMAIN,
    ENERGY_REPORT_MODE_CUMULATIVE,
    ENERGY_REPORT_MODE_INCREMENTAL,
)
from homeassistant.config_entries import SOURCE_USER
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType, InvalidData
from homeassistant.helpers import device_registry as dr, entity_registry as er

from tests.common import MockConfigEntry

pytestmark = pytest.mark.usefixtures("mock_setup_entry")


@pytest.mark.usefixtures("mock_tuya_login_control")
async def test_user_flow(
    hass: HomeAssistant,
    snapshot: SnapshotAssertion,
) -> None:
    """Test the full happy path user flow from start to finish."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_USER},
    )

    assert result.get("type") is FlowResultType.FORM
    assert result.get("step_id") == "user"

    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={CONF_USER_CODE: "12345"},
    )

    assert result2.get("type") is FlowResultType.FORM
    assert result2.get("step_id") == "scan"

    result3 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={},
    )

    assert result3.get("type") is FlowResultType.CREATE_ENTRY
    assert result3 == snapshot


async def test_user_flow_failed_qr_code(
    hass: HomeAssistant,
    mock_tuya_login_control: MagicMock,
) -> None:
    """Test an error occurring while retrieving the QR code."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_USER},
    )

    assert result.get("type") is FlowResultType.FORM
    assert result.get("step_id") == "user"

    # Something went wrong getting the QR code (like an invalid user code)
    mock_tuya_login_control.qr_code.return_value["success"] = False

    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={CONF_USER_CODE: "12345"},
    )

    assert result2.get("type") is FlowResultType.FORM
    assert result2.get("errors") == {"base": "login_error"}

    # This time it worked out
    mock_tuya_login_control.qr_code.return_value["success"] = True

    result3 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={CONF_USER_CODE: "12345"},
    )
    assert result3.get("step_id") == "scan"

    result3 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={},
    )

    assert result3.get("type") is FlowResultType.CREATE_ENTRY


async def test_user_flow_failed_scan(
    hass: HomeAssistant,
    mock_tuya_login_control: MagicMock,
) -> None:
    """Test an error occurring while verifying login."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_USER},
    )

    assert result.get("type") is FlowResultType.FORM
    assert result.get("step_id") == "user"

    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={CONF_USER_CODE: "12345"},
    )

    assert result2.get("type") is FlowResultType.FORM
    assert result2.get("step_id") == "scan"

    # Access has been denied, or the code hasn't been scanned yet
    good_values = mock_tuya_login_control.login_result.return_value
    mock_tuya_login_control.login_result.return_value = (
        False,
        {"msg": "oops", "code": 42},
    )

    result3 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={},
    )

    assert result3.get("type") is FlowResultType.FORM
    assert result3.get("errors") == {"base": "login_error"}

    # This time it worked out
    mock_tuya_login_control.login_result.return_value = good_values

    result4 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={},
    )

    assert result4.get("type") is FlowResultType.CREATE_ENTRY


@pytest.mark.usefixtures("mock_tuya_login_control")
async def test_reauth_flow(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    snapshot: SnapshotAssertion,
) -> None:
    """Test the reauthentication configuration flow."""
    mock_config_entry.add_to_hass(hass)

    result = await mock_config_entry.start_reauth_flow(hass)

    assert result.get("type") is FlowResultType.FORM
    assert result.get("step_id") == "scan"

    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={},
    )

    assert result2.get("type") is FlowResultType.ABORT
    assert result2.get("reason") == "reauth_successful"

    assert mock_config_entry == snapshot


@pytest.mark.usefixtures("mock_tuya_login_control")
async def test_reauth_flow_migration(
    hass: HomeAssistant,
    mock_old_config_entry: MockConfigEntry,
    snapshot: SnapshotAssertion,
) -> None:
    """Test the reauthentication configuration flow.

    This flow tests the migration from an old config entry.
    """
    mock_old_config_entry.add_to_hass(hass)

    # Ensure old data is there, new data is missing
    assert CONF_APP_TYPE in mock_old_config_entry.data
    assert CONF_USER_CODE not in mock_old_config_entry.data

    result = await mock_old_config_entry.start_reauth_flow(hass)

    assert result.get("type") is FlowResultType.FORM
    assert result.get("step_id") == "reauth_user_code"

    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={CONF_USER_CODE: "12345"},
    )

    assert result2.get("type") is FlowResultType.FORM
    assert result2.get("step_id") == "scan"

    result3 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={},
    )

    assert result3.get("type") is FlowResultType.ABORT
    assert result3.get("reason") == "reauth_successful"

    # Ensure the old data is gone, new data is present
    assert CONF_APP_TYPE not in mock_old_config_entry.data
    assert CONF_USER_CODE in mock_old_config_entry.data

    assert mock_old_config_entry == snapshot


async def test_reauth_flow_failed_qr_code(
    hass: HomeAssistant,
    mock_tuya_login_control: MagicMock,
    mock_old_config_entry: MockConfigEntry,
) -> None:
    """Test an error occurring while retrieving the QR code."""
    mock_old_config_entry.add_to_hass(hass)

    result = await mock_old_config_entry.start_reauth_flow(hass)

    # Something went wrong getting the QR code (like an invalid user code)
    mock_tuya_login_control.qr_code.return_value["success"] = False

    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={CONF_USER_CODE: "12345"},
    )

    assert result2.get("type") is FlowResultType.FORM
    assert result2.get("errors") == {"base": "login_error"}

    # This time it worked out
    mock_tuya_login_control.qr_code.return_value["success"] = True

    result3 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={CONF_USER_CODE: "12345"},
    )
    assert result3.get("step_id") == "scan"

    result3 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={},
    )

    assert result3.get("type") is FlowResultType.ABORT
    assert result3.get("reason") == "reauth_successful"


async def test_options_flow_no_energy_sensors(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test options flow when no energy sensors are present."""
    # Create a mock config entry
    mock_config_entry.add_to_hass(hass)

    # Create an options flow
    result = await hass.config_entries.options.async_init(mock_config_entry.entry_id)

    # Should show no_energy_devices step since no energy sensors
    assert result.get("type") is FlowResultType.FORM
    assert result.get("step_id") == "no_energy_devices"

    # User acknowledges the message
    result2 = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={},
    )

    # Should create empty entry
    assert result2.get("type") is FlowResultType.CREATE_ENTRY
    assert result2.get("data") == {}


async def test_options_flow_with_energy_sensors(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test options flow when energy sensors are present.

    This test covers:
    - Single device configuration (incremental/cumulative modes)
    - Multiple devices configuration
    - Empty configuration handling
    - Error handling for invalid input
    """
    # Add mock config entry
    mock_config_entry.add_to_hass(hass)

    # Create mock device first
    device_registry = dr.async_get(hass)
    device_entry = device_registry.async_get_or_create(
        config_entry_id=mock_config_entry.entry_id,
        identifiers={(DOMAIN, "test_device_1")},
        name="Test Device 1",
        manufacturer="Tuya",
    )

    # Mock entity registry with an energy sensor
    entity_registry = er.async_get(hass)
    entity_registry.async_get_or_create(
        domain="sensor",
        platform="tuya",
        unique_id="test_device_1_energy",
        config_entry=mock_config_entry,
        device_id=device_entry.id,
        original_device_class=SensorDeviceClass.ENERGY,
        capabilities={"state_class": "total_increasing"},
        original_name="Energy",
    )

    # Start options flow
    result = await hass.config_entries.options.async_init(mock_config_entry.entry_id)

    assert result.get("type") is FlowResultType.FORM
    assert result.get("step_id") == "init"

    # Configure with device-specific incremental mode
    result2 = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={
            "Test Device 1 [test_device_1] [Energy]": ENERGY_REPORT_MODE_INCREMENTAL
        },
    )

    assert result2.get("type") is FlowResultType.CREATE_ENTRY
    assert result2.get("data") == {
        "device_energy_modes": {"test_device_1": ENERGY_REPORT_MODE_INCREMENTAL}
    }

    # Configure with device-specific cumulative mode
    result3 = await hass.config_entries.options.async_init(mock_config_entry.entry_id)
    result4 = await hass.config_entries.options.async_configure(
        result3["flow_id"],
        user_input={
            "Test Device 1 [test_device_1] [Energy]": ENERGY_REPORT_MODE_CUMULATIVE
        },
    )

    assert result4.get("type") is FlowResultType.CREATE_ENTRY
    assert result4.get("data") == {
        "device_energy_modes": {"test_device_1": ENERGY_REPORT_MODE_CUMULATIVE}
    }

    # Configure with multiple devices
    device_entry2 = device_registry.async_get_or_create(
        config_entry_id=mock_config_entry.entry_id,
        identifiers={(DOMAIN, "test_device_2")},
        name="Test Device 2",
        manufacturer="Tuya",
    )

    entity_registry.async_get_or_create(
        domain="sensor",
        platform="tuya",
        unique_id="test_device_2_energy",
        config_entry=mock_config_entry,
        device_id=device_entry2.id,
        original_device_class=SensorDeviceClass.ENERGY,
        capabilities={"state_class": "total_increasing"},
        original_name="Energy Storage",
    )

    result5 = await hass.config_entries.options.async_init(mock_config_entry.entry_id)

    result6 = await hass.config_entries.options.async_configure(
        result5["flow_id"],
        user_input={
            "Test Device 2 [test_device_2] [Energy Storage]": ENERGY_REPORT_MODE_CUMULATIVE
        },
    )

    assert result6.get("type") is FlowResultType.CREATE_ENTRY
    assert result6.get("data") == {
        "device_energy_modes": {
            "test_device_1": ENERGY_REPORT_MODE_CUMULATIVE,
            "test_device_2": ENERGY_REPORT_MODE_CUMULATIVE,
        }
    }

    # Edge case: no selection, should not fail
    result7 = await hass.config_entries.options.async_init(mock_config_entry.entry_id)

    result8 = await hass.config_entries.options.async_configure(
        result7["flow_id"],
        user_input={},
    )

    assert result8.get("type") is FlowResultType.CREATE_ENTRY
    assert result8.get("data") == {
        "device_energy_modes": {
            "test_device_1": ENERGY_REPORT_MODE_CUMULATIVE,
            "test_device_2": ENERGY_REPORT_MODE_CUMULATIVE,
        }
    }

    # Error handling: invalid mode
    result9 = await hass.config_entries.options.async_init(mock_config_entry.entry_id)

    # This should cause a validation error, so we expect it to raise an exception
    with pytest.raises(InvalidData):
        await hass.config_entries.options.async_configure(
            result9["flow_id"],
            user_input={"Test Device 1 [test_device_1] [Energy]": "invalid_mode"},
        )
