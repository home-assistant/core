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
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.helpers import entity_registry as er

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
    options_flow = hass.config_entries.options.async_init(mock_config_entry.entry_id)

    result = await hass.config_entries.options.async_configure(
        options_flow["flow_id"],
        user_input=None,
    )

    # Should complete immediately with no options since no energy sensors
    assert result.get("type") is FlowResultType.CREATE_ENTRY
    assert result.get("data") == {}


async def test_options_flow_with_energy_sensors(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test options flow when energy sensors are present."""
    # Add mock config entry
    mock_config_entry.add_to_hass(hass)

    # Mock entity registry with an energy sensor
    entity_registry = er.async_get(hass)
    entity_registry.async_get_or_create(
        domain="sensor",
        platform="tuya",
        unique_id="test_device_1_energy",
        config_entry=mock_config_entry,
        device_class=SensorDeviceClass.ENERGY,
    )

    # Start options flow
    result = await hass.config_entries.options.async_init(mock_config_entry.entry_id)

    assert result.get("type") is FlowResultType.FORM
    assert result.get("step_id") == "init"

    # Configure with device-specific incremental mode
    result2 = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={"energy_report_mode_test_device_1": ENERGY_REPORT_MODE_INCREMENTAL},
    )

    assert result2.get("type") is FlowResultType.CREATE_ENTRY
    assert result2.get("data") == {
        "device_energy_modes": {"test_device_1": ENERGY_REPORT_MODE_INCREMENTAL}
    }

    # Configure with device-specific cumulative mode
    result2 = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={"energy_report_mode_test_device_1": ENERGY_REPORT_MODE_CUMULATIVE},
    )

    assert result2.get("type") is FlowResultType.CREATE_ENTRY
    assert result2.get("data") == {
        "device_energy_modes": {"test_device_1": ENERGY_REPORT_MODE_CUMULATIVE}
    }

    # Configure with multiple devices
    entity_registry.async_get_or_create(
        domain="sensor",
        platform="tuya",
        unique_id="test_device_2_energy",
        config_entry=mock_config_entry,
        device_class=SensorDeviceClass.ENERGY,
    )

    result3 = await hass.config_entries.options.async_init(mock_config_entry.entry_id)

    result5 = await hass.config_entries.options.async_configure(
        result3["flow_id"],
        user_input={"energy_report_mode_test_device_2": ENERGY_REPORT_MODE_CUMULATIVE},
    )

    assert result5.get("type") is FlowResultType.CREATE_ENTRY
    assert result5.get("data") == {
        "device_energy_modes": {
            "test_device_1": ENERGY_REPORT_MODE_INCREMENTAL,
            "test_device_2": ENERGY_REPORT_MODE_CUMULATIVE,
        }
    }

    # Edge case: no selection, should not fail
    result6 = await hass.config_entries.options.async_init(mock_config_entry.entry_id)

    result7 = await hass.config_entries.options.async_configure(
        result6["flow_id"],
        user_input={},
    )

    assert result7.get("type") is FlowResultType.CREATE_ENTRY
    assert result7.get("data") == {
        "device_energy_modes": {
            "test_device_1": ENERGY_REPORT_MODE_INCREMENTAL,
            "test_device_2": ENERGY_REPORT_MODE_CUMULATIVE,
        }
    }

    # Error handling: invalid mode
    result8 = await hass.config_entries.options.async_init(mock_config_entry.entry_id)

    result9 = await hass.config_entries.options.async_configure(
        result8["flow_id"],
        user_input={"energy_report_mode_test_device_1": "invalid_mode"},
    )

    assert result9.get("type") is FlowResultType.FORM
    assert result9.get("errors") == {"base": "unknown_energy_report_mode"}
