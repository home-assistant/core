"""Test Hikvision binary sensors."""

import logging
from unittest.mock import MagicMock

import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.binary_sensor import BinarySensorDeviceClass
from homeassistant.components.hikvision.const import DOMAIN
from homeassistant.const import (
    ATTR_DEVICE_CLASS,
    ATTR_LAST_TRIP_TIME,
    CONF_HOST,
    CONF_NAME,
    CONF_PASSWORD,
    CONF_PORT,
    CONF_SSL,
    CONF_USERNAME,
    STATE_OFF,
    Platform,
)
from homeassistant.core import DOMAIN as HOMEASSISTANT_DOMAIN, HomeAssistant
from homeassistant.helpers import (
    device_registry as dr,
    entity_registry as er,
    issue_registry as ir,
)
from homeassistant.setup import async_setup_component

from . import setup_integration
from .conftest import (
    TEST_DEVICE_ID,
    TEST_DEVICE_NAME,
    TEST_HOST,
    TEST_PASSWORD,
    TEST_PORT,
    TEST_USERNAME,
)

from tests.common import MockConfigEntry, snapshot_platform


@pytest.fixture
def platforms() -> list[Platform]:
    """Platforms, which should be loaded during the test."""
    return [Platform.BINARY_SENSOR]


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_all_entities(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_hikcamera: MagicMock,
    entity_registry: er.EntityRegistry,
    snapshot: SnapshotAssertion,
) -> None:
    """Test all binary sensor entities."""
    await setup_integration(hass, mock_config_entry)
    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)


async def test_binary_sensors_created(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_hikcamera: MagicMock,
) -> None:
    """Test binary sensors are created for each event type."""
    await setup_integration(hass, mock_config_entry)

    # Check Motion sensor (camera type doesn't include channel in name)
    state = hass.states.get("binary_sensor.front_camera_motion")
    assert state is not None
    assert state.state == STATE_OFF
    assert state.attributes.get(ATTR_DEVICE_CLASS) == BinarySensorDeviceClass.MOTION
    assert ATTR_LAST_TRIP_TIME in state.attributes

    # Check Line Crossing sensor
    state = hass.states.get("binary_sensor.front_camera_line_crossing")
    assert state is not None
    assert state.state == STATE_OFF
    assert state.attributes.get(ATTR_DEVICE_CLASS) == BinarySensorDeviceClass.MOTION


async def test_binary_sensor_device_info(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_hikcamera: MagicMock,
    device_registry: dr.DeviceRegistry,
) -> None:
    """Test binary sensors are linked to device."""
    await setup_integration(hass, mock_config_entry)

    device_entry = device_registry.async_get_device(
        identifiers={(DOMAIN, TEST_DEVICE_ID)}
    )
    assert device_entry is not None
    assert device_entry.name == TEST_DEVICE_NAME
    assert device_entry.manufacturer == "Hikvision"
    assert device_entry.model == "Camera"


async def test_binary_sensor_callback_registered(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_hikcamera: MagicMock,
) -> None:
    """Test that callback is registered with pyhik."""
    await setup_integration(hass, mock_config_entry)

    # Verify callback was registered for each sensor
    assert mock_hikcamera.return_value.add_update_callback.call_count == 2


async def test_binary_sensor_no_sensors(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_hikcamera: MagicMock,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test setup when device has no sensors."""
    mock_hikcamera.return_value.current_event_states = None

    with caplog.at_level(logging.WARNING):
        await setup_integration(hass, mock_config_entry)

    # No binary sensors should be created
    states = hass.states.async_entity_ids("binary_sensor")
    assert len(states) == 0

    # Verify warning was logged
    assert "has no sensors available" in caplog.text


@pytest.mark.parametrize("amount_of_channels", [2])
async def test_binary_sensor_nvr_device(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_hikcamera: MagicMock,
    device_registry: dr.DeviceRegistry,
) -> None:
    """Test binary sensor naming for NVR devices."""
    mock_hikcamera.return_value.get_type = "NVR"
    mock_hikcamera.return_value.current_event_states = {
        "Motion": [(True, 1), (False, 2)],
    }

    await setup_integration(hass, mock_config_entry)

    # Verify NVR channel devices are created with via_device linking
    channel_1_device = device_registry.async_get_device(
        identifiers={(DOMAIN, f"{TEST_DEVICE_ID}_1")}
    )
    assert channel_1_device is not None
    assert channel_1_device.via_device_id is not None

    channel_2_device = device_registry.async_get_device(
        identifiers={(DOMAIN, f"{TEST_DEVICE_ID}_2")}
    )
    assert channel_2_device is not None
    assert channel_2_device.via_device_id is not None

    # Verify sensors are created (entity IDs depend on translation loading)
    states = hass.states.async_entity_ids("binary_sensor")
    assert len(states) == 2


async def test_binary_sensor_state_on(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_hikcamera: MagicMock,
) -> None:
    """Test binary sensor state when on."""
    mock_hikcamera.return_value.fetch_attributes.return_value = (
        True,
        None,
        None,
        "2024-01-01T12:00:00Z",
    )

    await setup_integration(hass, mock_config_entry)

    state = hass.states.get("binary_sensor.front_camera_motion")
    assert state is not None
    assert state.state == "on"


async def test_binary_sensor_device_class_unknown(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_hikcamera: MagicMock,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test unknown sensor types are logged and skipped."""
    mock_hikcamera.return_value.current_event_states = {
        "Unknown Event": [(False, 1)],
    }

    with caplog.at_level(logging.WARNING):
        await setup_integration(hass, mock_config_entry)

    # No entity should be created for unknown sensor types
    states = hass.states.async_entity_ids("binary_sensor")
    assert len(states) == 0

    # Verify warning was logged for unknown sensor type
    assert "Unknown Hikvision sensor type 'Unknown Event'" in caplog.text


async def test_yaml_import_creates_deprecation_issue(
    hass: HomeAssistant,
    mock_hikcamera: MagicMock,
    issue_registry: ir.IssueRegistry,
) -> None:
    """Test YAML import creates deprecation issue."""
    await async_setup_component(
        hass,
        "binary_sensor",
        {
            "binary_sensor": {
                "platform": DOMAIN,
                CONF_HOST: TEST_HOST,
                CONF_PORT: TEST_PORT,
                CONF_USERNAME: TEST_USERNAME,
                CONF_PASSWORD: TEST_PASSWORD,
                CONF_SSL: False,
            }
        },
    )
    await hass.async_block_till_done()

    # Check that deprecation issue was created in homeassistant domain
    issue = issue_registry.async_get_issue(
        HOMEASSISTANT_DOMAIN, f"deprecated_yaml_{DOMAIN}"
    )
    assert issue is not None
    assert issue.severity == ir.IssueSeverity.WARNING


async def test_yaml_import_with_name(
    hass: HomeAssistant,
    mock_hikcamera: MagicMock,
) -> None:
    """Test YAML import uses custom name for config entry."""
    await async_setup_component(
        hass,
        "binary_sensor",
        {
            "binary_sensor": {
                "platform": DOMAIN,
                CONF_NAME: "Custom Camera Name",
                CONF_HOST: TEST_HOST,
                CONF_PORT: TEST_PORT,
                CONF_USERNAME: TEST_USERNAME,
                CONF_PASSWORD: TEST_PASSWORD,
                CONF_SSL: False,
            }
        },
    )
    await hass.async_block_till_done()

    # Check that the config entry was created with the custom name
    entries = hass.config_entries.async_entries(DOMAIN)
    assert len(entries) == 1
    assert entries[0].title == "Custom Camera Name"


async def test_yaml_import_abort_creates_issue(
    hass: HomeAssistant,
    mock_hikcamera: MagicMock,
    issue_registry: ir.IssueRegistry,
) -> None:
    """Test YAML import creates issue when import is aborted."""
    mock_hikcamera.return_value.get_id = None

    await async_setup_component(
        hass,
        "binary_sensor",
        {
            "binary_sensor": {
                "platform": DOMAIN,
                CONF_HOST: TEST_HOST,
                CONF_PORT: TEST_PORT,
                CONF_USERNAME: TEST_USERNAME,
                CONF_PASSWORD: TEST_PASSWORD,
                CONF_SSL: False,
            }
        },
    )
    await hass.async_block_till_done()

    # Check that import failure issue was created
    issue = issue_registry.async_get_issue(
        DOMAIN, "deprecated_yaml_import_issue_cannot_connect"
    )
    assert issue is not None
    assert issue.severity == ir.IssueSeverity.WARNING


async def test_binary_sensor_update_callback(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_hikcamera: MagicMock,
) -> None:
    """Test binary sensor state updates via callback."""
    await setup_integration(hass, mock_config_entry)

    state = hass.states.get("binary_sensor.front_camera_motion")
    assert state is not None
    assert state.state == STATE_OFF

    # Simulate state change via callback
    mock_hikcamera.return_value.fetch_attributes.return_value = (
        True,
        None,
        None,
        "2024-01-01T12:00:00Z",
    )

    # Get the registered callback and call it
    add_callback_call = mock_hikcamera.return_value.add_update_callback.call_args_list[
        0
    ]
    callback_func = add_callback_call[0][0]
    callback_func("motion detected")

    # Wait for the event loop to process the scheduled state update
    # (callback uses call_soon_threadsafe to schedule update in event loop)
    await hass.async_block_till_done()

    # Verify state was updated
    state = hass.states.get("binary_sensor.front_camera_motion")
    assert state is not None
    assert state.state == "on"
