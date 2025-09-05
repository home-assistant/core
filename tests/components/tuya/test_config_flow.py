"""Tests for the Tuya config flow."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.sensor import SensorDeviceClass
from homeassistant.components.tuya.config_flow import TuyaOptionsFlow
from homeassistant.components.tuya.const import CONF_APP_TYPE, CONF_USER_CODE, DOMAIN
from homeassistant.config_entries import SOURCE_USER
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.helpers import device_registry as dr, entity_registry as er

from .conftest import complete_options_flow

from tests.common import MockConfigEntry

pytestmark = pytest.mark.usefixtures("mock_setup_entry")

# Test constants
SENSOR_DOMAIN = "sensor"
TUYA_PLATFORM = "tuya"
TUYA_MANUFACTURER = "Tuya"

# Common capabilities
ENERGY_CAPABILITIES = {"state_class": "total_increasing"}
MEASUREMENT_CAPABILITIES = {"state_class": "measurement"}

# Test ID prefixes
TEST_DEVICE_PREFIX = "test_device"
TEST_ENTITY_PREFIX = "test_entity"


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


@pytest.mark.parametrize(
    ("device_id", "device_name", "sensor_count", "description"),
    [
        (
            "test_device_many_sensors",
            "Device Many Sensors",
            5,
            "device with many sensors",
        ),
        ("test_device_no_sensors", "Device No Sensors", 0, "device with no sensors"),
    ],
)
async def test_options_flow_device_sensor_scenarios(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    device_id: str,
    device_name: str,
    sensor_count: int,
    description: str,
) -> None:
    """Test options flow with different device sensor scenarios."""
    mock_config_entry.add_to_hass(hass)
    device_registry = dr.async_get(hass)
    entity_registry = er.async_get(hass)

    # Create device
    device = device_registry.async_get_or_create(
        config_entry_id=mock_config_entry.entry_id,
        identifiers={(DOMAIN, device_id)},
        name=device_name,
        manufacturer=TUYA_MANUFACTURER,
    )

    # Create sensors if needed
    if sensor_count > 0:
        for i in range(sensor_count):
            entity_registry.async_get_or_create(
                domain=SENSOR_DOMAIN,
                platform=TUYA_PLATFORM,
                unique_id=f"{TEST_ENTITY_PREFIX}_{device_id}_{i}",
                config_entry=mock_config_entry,
                device_id=device.id,
                original_device_class=SensorDeviceClass.ENERGY,
                capabilities=ENERGY_CAPABILITIES,
                original_name=f"Energy Sensor {i}",
            )

    # Test options flow
    await complete_options_flow(hass, mock_config_entry)


async def test_options_flow_invalid_entities(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test options flow with invalid entities to cover continue statements."""
    mock_config_entry.add_to_hass(hass)
    device_registry = dr.async_get(hass)
    entity_registry = er.async_get(hass)

    # Create a valid device
    device = device_registry.async_get_or_create(
        config_entry_id=mock_config_entry.entry_id,
        identifiers={(DOMAIN, f"{TEST_DEVICE_PREFIX}_invalid")},
        name="Device Invalid",
        manufacturer=TUYA_MANUFACTURER,
    )

    # Create entity without device_id (line 351)
    entity_registry.async_get_or_create(
        domain=SENSOR_DOMAIN,
        platform=TUYA_PLATFORM,
        unique_id=f"{TEST_ENTITY_PREFIX}_no_device",
        config_entry=mock_config_entry,
        device_id=None,
        original_name="Energy No Device",
        original_device_class=SensorDeviceClass.ENERGY,
        capabilities=ENERGY_CAPABILITIES,
    )

    # Create entity with wrong device class (line 351)
    entity_registry.async_get_or_create(
        domain=SENSOR_DOMAIN,
        platform=TUYA_PLATFORM,
        unique_id=f"{TEST_ENTITY_PREFIX}_wrong_class",
        config_entry=mock_config_entry,
        device_id=device.id,
        original_name="Temperature Sensor",
        original_device_class=SensorDeviceClass.TEMPERATURE,
        capabilities=MEASUREMENT_CAPABILITIES,
    )

    # Create entity without capabilities (line 351)
    entity_registry.async_get_or_create(
        domain=SENSOR_DOMAIN,
        platform=TUYA_PLATFORM,
        unique_id=f"{TEST_ENTITY_PREFIX}_no_capabilities",
        config_entry=mock_config_entry,
        device_id=device.id,
        original_name="Energy No Capabilities",
        original_device_class=SensorDeviceClass.ENERGY,
        capabilities=None,
    )

    # Test options flow
    await complete_options_flow(hass, mock_config_entry)


async def test_options_flow_wrong_domain_device(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test options flow with device from wrong domain (line 357)."""
    mock_config_entry.add_to_hass(hass)
    device_registry = dr.async_get(hass)
    entity_registry = er.async_get(hass)

    # Create device with wrong domain identifiers
    device = device_registry.async_get_or_create(
        config_entry_id=mock_config_entry.entry_id,
        identifiers={("wrong_domain", f"{TEST_DEVICE_PREFIX}_wrong")},
        name="Device Wrong Domain",
        manufacturer="Other",
    )

    # Create entity for this device
    entity_registry.async_get_or_create(
        domain=SENSOR_DOMAIN,
        platform=TUYA_PLATFORM,
        unique_id=f"{TEST_ENTITY_PREFIX}_wrong_domain",
        config_entry=mock_config_entry,
        device_id=device.id,
        original_name="Energy Wrong Domain",
        original_device_class=SensorDeviceClass.ENERGY,
        capabilities=ENERGY_CAPABILITIES,
    )

    # Test options flow
    await complete_options_flow(hass, mock_config_entry)


async def test_options_flow_empty_identifiers(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test options flow with device having empty identifiers (line 391)."""
    mock_config_entry.add_to_hass(hass)
    device_registry = dr.async_get(hass)
    entity_registry = er.async_get(hass)

    # Create device with valid identifiers first
    device = device_registry.async_get_or_create(
        config_entry_id=mock_config_entry.entry_id,
        identifiers={(DOMAIN, f"{TEST_DEVICE_PREFIX}_empty")},
        name="Device Empty",
        manufacturer=TUYA_MANUFACTURER,
    )

    # Create entity for this device
    entity_registry.async_get_or_create(
        domain=SENSOR_DOMAIN,
        platform=TUYA_PLATFORM,
        unique_id=f"{TEST_ENTITY_PREFIX}_empty",
        config_entry=mock_config_entry,
        device_id=device.id,
        original_name="Energy Empty",
        original_device_class=SensorDeviceClass.ENERGY,
        capabilities=ENERGY_CAPABILITIES,
    )

    # Clear device identifiers to test line 391
    device_registry.async_update_device(device.id, new_identifiers=set())

    # Test options flow
    await complete_options_flow(hass, mock_config_entry)


@pytest.mark.parametrize(
    ("sensors", "expected_suffix"),
    [
        ([], "No sensors"),
        (["Sensor 1", "Sensor 2", "Sensor 3"], "Sensor 1, Sensor 2, Sensor 3"),
        (
            ["Sensor 1", "Sensor 2", "Sensor 3", "Sensor 4", "Sensor 5"],
            "Sensor 1, Sensor 2, Sensor 3 (+2 more)",
        ),
    ],
)
async def test_format_device_list_method(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    sensors: list[str],
    expected_suffix: str,
) -> None:
    """Test _format_device_list method to cover all branches."""
    mock_config_entry.add_to_hass(hass)

    # Create a flow instance
    flow = TuyaOptionsFlow()
    flow.hass = hass

    # Test with different sensor configurations
    energy_devices = {
        "test_device": {
            "name": "Test Device",
            "sensors": sensors,
        }
    }
    result = flow._format_device_list(energy_devices)
    assert result == [("test_device", f"Test Device &|& {expected_suffix}")]
