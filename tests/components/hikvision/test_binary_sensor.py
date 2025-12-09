"""Test Hikvision binary sensors."""

from unittest.mock import MagicMock, patch

import requests

from homeassistant.components.binary_sensor import BinarySensorDeviceClass
from homeassistant.components.hikvision.const import DOMAIN
from homeassistant.const import (
    ATTR_DEVICE_CLASS,
    ATTR_LAST_TRIP_TIME,
    CONF_HOST,
    CONF_PASSWORD,
    CONF_PORT,
    CONF_SSL,
    CONF_USERNAME,
    STATE_OFF,
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

from tests.common import MockConfigEntry


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

    # Check Line Crossing sensor
    state = hass.states.get("binary_sensor.front_camera_line_crossing")
    assert state is not None
    assert state.state == STATE_OFF
    assert state.attributes.get(ATTR_DEVICE_CLASS) == BinarySensorDeviceClass.MOTION


async def test_binary_sensor_unique_id(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_hikcamera: MagicMock,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test binary sensors have correct unique IDs."""
    await setup_integration(hass, mock_config_entry)

    entity_entry = entity_registry.async_get("binary_sensor.front_camera_motion")
    assert entity_entry is not None
    assert entity_entry.unique_id == f"{TEST_DEVICE_ID}_Motion_1"


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


async def test_binary_sensor_attributes(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_hikcamera: MagicMock,
) -> None:
    """Test binary sensor extra state attributes."""
    await setup_integration(hass, mock_config_entry)

    state = hass.states.get("binary_sensor.front_camera_motion")
    assert state is not None
    assert ATTR_LAST_TRIP_TIME in state.attributes
    assert state.attributes[ATTR_LAST_TRIP_TIME] == "2024-01-01T00:00:00Z"


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
) -> None:
    """Test setup when device has no sensors."""
    mock_hikcamera.return_value.current_event_states = None

    await setup_integration(hass, mock_config_entry)

    # No binary sensors should be created
    states = hass.states.async_entity_ids("binary_sensor")
    assert len(states) == 0


async def test_binary_sensor_nvr_device(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_hikcamera: MagicMock,
) -> None:
    """Test binary sensor naming for NVR devices."""
    mock_hikcamera.return_value.get_type = "NVR"
    mock_hikcamera.return_value.current_event_states = {
        "Motion": [(True, 1), (False, 2)],
    }

    await setup_integration(hass, mock_config_entry)

    # NVR sensors should include channel number in name
    state = hass.states.get("binary_sensor.front_camera_motion_1")
    assert state is not None

    state = hass.states.get("binary_sensor.front_camera_motion_2")
    assert state is not None


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
) -> None:
    """Test binary sensor with unknown device class."""
    mock_hikcamera.return_value.current_event_states = {
        "Unknown Event": [(False, 1)],
    }

    await setup_integration(hass, mock_config_entry)

    state = hass.states.get("binary_sensor.front_camera_unknown_event")
    assert state is not None
    assert state.attributes.get(ATTR_DEVICE_CLASS) is None


async def test_yaml_import_creates_deprecation_issue(
    hass: HomeAssistant,
    mock_hikcamera: MagicMock,
) -> None:
    """Test YAML import creates deprecation issue."""
    with patch(
        "homeassistant.components.hikvision.config_flow.HikCamera",
        autospec=True,
    ) as hikcamera_mock:
        camera = hikcamera_mock.return_value
        camera.get_id.return_value = TEST_DEVICE_ID
        camera.get_name = TEST_DEVICE_NAME

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
    issue_registry = ir.async_get(hass)
    issue = issue_registry.async_get_issue(
        HOMEASSISTANT_DOMAIN, f"deprecated_yaml_{DOMAIN}"
    )
    assert issue is not None
    assert issue.severity == ir.IssueSeverity.WARNING


async def test_yaml_import_creates_failure_issue_on_error(
    hass: HomeAssistant,
) -> None:
    """Test YAML import creates failure issue when import fails."""
    with patch(
        "homeassistant.components.hikvision.config_flow.HikCamera",
        autospec=True,
    ) as hikcamera_mock:
        hikcamera_mock.side_effect = requests.exceptions.RequestException(
            "Connection failed"
        )

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

    # Check that failure issue was created
    issue_registry = ir.async_get(hass)
    issue = issue_registry.async_get_issue(
        DOMAIN, "deprecated_yaml_import_issue_cannot_connect"
    )
    assert issue is not None
    assert issue.severity == ir.IssueSeverity.WARNING


async def test_yaml_import_no_issue_on_already_configured(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test YAML import creates deprecation issue even when already configured."""
    mock_config_entry.add_to_hass(hass)

    with patch(
        "homeassistant.components.hikvision.config_flow.HikCamera",
        autospec=True,
    ) as hikcamera_mock:
        camera = hikcamera_mock.return_value
        camera.get_id.return_value = TEST_DEVICE_ID
        camera.get_name = TEST_DEVICE_NAME

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

    # Check that deprecation issue was created (not a failure issue)
    issue_registry = ir.async_get(hass)
    issue = issue_registry.async_get_issue(
        HOMEASSISTANT_DOMAIN, f"deprecated_yaml_{DOMAIN}"
    )
    assert issue is not None
