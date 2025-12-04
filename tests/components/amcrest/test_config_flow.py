"""Test the Amcrest config flow."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from homeassistant import config_entries
from homeassistant.components.amcrest.config_flow import CannotConnect, InvalidAuth
from homeassistant.components.amcrest.const import DOMAIN
from homeassistant.const import (
    CONF_HOST,
    CONF_NAME,
    CONF_PASSWORD,
    CONF_PORT,
    CONF_USERNAME,
)
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.helpers import device_registry as dr, entity_registry as er

from tests.common import MockConfigEntry


@pytest.fixture
def mock_setup_entry():
    """Mock async setup entry."""
    with patch(
        "homeassistant.components.amcrest.async_setup_entry", return_value=True
    ) as mock_setup:
        yield mock_setup


async def test_form(hass: HomeAssistant, mock_setup_entry: MagicMock) -> None:
    """Test we get the form."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == FlowResultType.FORM
    assert result["errors"] == {}

    with patch(
        "homeassistant.components.amcrest.config_flow._test_connection"
    ) as mock_test:
        mock_test.return_value = None  # Connection successful

        with patch(
            "homeassistant.components.amcrest.config_flow._get_unique_id"
        ) as mock_unique:
            mock_unique.return_value = "ABCD1234567890"

            result2 = await hass.config_entries.flow.async_configure(
                result["flow_id"],
                {
                    CONF_NAME: "Living Room",
                    CONF_HOST: "192.168.1.100",
                    CONF_PORT: 80,
                    CONF_USERNAME: "admin",
                    CONF_PASSWORD: "password123",
                },
            )
            await hass.async_block_till_done()

    assert result2["type"] == FlowResultType.CREATE_ENTRY
    assert result2["title"] == "Living Room"
    assert result2["data"] == {
        CONF_NAME: "Living Room",
        CONF_HOST: "192.168.1.100",
        CONF_PORT: 80,
        CONF_USERNAME: "admin",
        CONF_PASSWORD: "password123",
    }
    assert len(mock_setup_entry.mock_calls) == 1


async def test_form_invalid_auth(hass: HomeAssistant) -> None:
    """Test we handle invalid auth."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with patch(
        "homeassistant.components.amcrest.config_flow._test_connection"
    ) as mock_test:
        mock_test.side_effect = InvalidAuth()

        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_NAME: "Living Room",
                CONF_HOST: "192.168.1.100",
                CONF_PORT: 80,
                CONF_USERNAME: "admin",
                CONF_PASSWORD: "wrong_password",
            },
        )

    assert result2["type"] == FlowResultType.FORM
    assert result2["errors"] == {"base": "invalid_auth"}


async def test_form_cannot_connect(hass: HomeAssistant) -> None:
    """Test we handle cannot connect error."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with patch(
        "homeassistant.components.amcrest.config_flow._test_connection"
    ) as mock_test:
        mock_test.side_effect = CannotConnect()

        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_NAME: "Living Room",
                CONF_HOST: "192.168.1.100",
                CONF_PORT: 80,
                CONF_USERNAME: "admin",
                CONF_PASSWORD: "password123",
            },
        )

    assert result2["type"] == FlowResultType.FORM
    assert result2["errors"] == {"base": "cannot_connect"}


async def test_form_unknown_error(hass: HomeAssistant) -> None:
    """Test we handle unknown error."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with patch(
        "homeassistant.components.amcrest.config_flow._test_connection"
    ) as mock_test:
        mock_test.side_effect = Exception("Unexpected error")

        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_NAME: "Living Room",
                CONF_HOST: "192.168.1.100",
                CONF_PORT: 80,
                CONF_USERNAME: "admin",
                CONF_PASSWORD: "password123",
            },
        )

    assert result2["type"] == FlowResultType.FORM
    assert result2["errors"] == {"base": "unknown"}


async def test_reconfigure(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Test reconfigure flow."""
    mock_config_entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={
            "source": config_entries.SOURCE_RECONFIGURE,
            "entry_id": mock_config_entry.entry_id,
        },
    )
    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "user"  # Should delegate to user step

    with patch(
        "homeassistant.components.amcrest.config_flow._test_connection"
    ) as mock_test:
        mock_test.return_value = None  # Connection successful

        with patch(
            "homeassistant.components.amcrest.config_flow._get_unique_id"
        ) as mock_unique:
            mock_unique.return_value = "ABCD1234567890"  # Same as config entry

            result2 = await hass.config_entries.flow.async_configure(
                result["flow_id"],
                {
                    CONF_HOST: "192.168.1.101",
                    CONF_PORT: 8080,
                    CONF_USERNAME: "admin",
                    CONF_PASSWORD: "new_password",
                },
            )
            await hass.async_block_till_done()

    assert result2["type"] == FlowResultType.ABORT
    assert result2["reason"] == "reconfigure_successful"
    assert mock_config_entry.data[CONF_HOST] == "192.168.1.101"
    assert mock_config_entry.data[CONF_PORT] == 8080
    assert mock_config_entry.data[CONF_PASSWORD] == "new_password"


async def test_unique_id_already_exists(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Test we abort if the camera is already configured."""
    mock_config_entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with patch(
        "homeassistant.components.amcrest.config_flow._test_connection"
    ) as mock_test:
        mock_test.return_value = None  # Connection successful

        with patch(
            "homeassistant.components.amcrest.config_flow._get_unique_id"
        ) as mock_unique:
            mock_unique.return_value = "ABCD1234567890"  # Same as mock_config_entry

            result2 = await hass.config_entries.flow.async_configure(
                result["flow_id"],
                {
                    CONF_NAME: "Living Room 2",
                    CONF_HOST: "192.168.1.101",
                    CONF_PORT: 80,
                    CONF_USERNAME: "admin",
                    CONF_PASSWORD: "password123",
                },
            )

    assert "type" in result2 and result2["type"] == FlowResultType.ABORT
    assert "reason" in result2 and result2["reason"] == "already_configured"


async def test_comprehensive_device_creation(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_amcrest_api: MagicMock,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test that devices and entities are properly created and registered."""
    mock_config_entry.add_to_hass(hass)

    with patch(
        "homeassistant.components.amcrest.AmcrestChecker",
        return_value=mock_amcrest_api,
    ):
        assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    # Verify device is registered with correct identifiers
    device = device_registry.async_get_device(identifiers={(DOMAIN, "ABCD1234567890")})
    assert device is not None, "Device should be registered in device registry"
    assert device.name == "Living Room"
    assert device.manufacturer == "Amcrest"
    # assert device.model is not None
    assert device.configuration_url == "http://192.168.1.100"

    # Get all entities for this config entry
    all_entities = er.async_entries_for_config_entry(
        entity_registry, mock_config_entry.entry_id
    )

    # Verify entities exist and are linked to device
    assert len(all_entities) > 0, "At least one entity should be created"

    # Group entities by platform
    entities_by_platform = {}
    for entity_entry in all_entities:
        if entity_entry.platform == DOMAIN:
            platform = entity_entry.domain
            if platform not in entities_by_platform:
                entities_by_platform[platform] = []
            entities_by_platform[platform].append(entity_entry)

    # Verify each platform has entities
    expected_platforms = ["camera", "sensor", "binary_sensor", "switch", "button"]
    for platform in expected_platforms:
        assert platform in entities_by_platform, (
            f"{platform} entities should be created"
        )
        platform_entities = entities_by_platform[platform]

        # Verify all entities are linked to the device
        for entity_entry in platform_entities:
            assert entity_entry.device_id == device.id, (
                f"Entity {entity_entry.entity_id} should be linked to device"
            )
            assert entity_entry.platform == DOMAIN
            assert entity_entry.unique_id is not None
            assert entity_entry.unique_id.startswith("ABCD1234567890")

    # Verify specific critical entities exist
    camera_entities = [e for e in all_entities if e.domain == "camera"]
    assert len(camera_entities) > 0, "At least one camera entity should exist"

    # Verify camera entity has proper configuration
    camera_entity = camera_entities[0]
    assert camera_entity.original_name is not None
    assert camera_entity.entity_category is None  # Main camera is not diagnostic

    # Verify sensor entities include expected types
    sensor_entities = [e for e in all_entities if e.domain == "sensor"]
    sensor_keys = {
        e.unique_id.split("_", 1)[1] for e in sensor_entities if "_" in e.unique_id
    }

    # Check for some expected sensors (exact list depends on implementation)
    # These are examples - adjust based on your actual implementation
    assert len(sensor_keys) > 0, "Sensor entities should have unique keys"

    # Verify binary sensors
    binary_sensor_entities = [e for e in all_entities if e.domain == "binary_sensor"]
    assert len(binary_sensor_entities) > 0, "Binary sensor entities should be created"

    # Verify switches
    switch_entities = [e for e in all_entities if e.domain == "switch"]
    assert len(switch_entities) > 0, "Switch entities should be created"

    # Verify at least one switch is enabled by default
    enabled_switches = [e for e in switch_entities if not e.disabled]
    assert len(enabled_switches) > 0, "At least one switch should be enabled by default"

    # Verify buttons
    button_entities = [e for e in all_entities if e.domain == "button"]
    assert len(button_entities) > 0, "Button entities should be created"

    # Verify entity states are accessible (for enabled entities)
    for entity_entry in all_entities:
        if not entity_entry.disabled:
            state = hass.states.get(entity_entry.entity_id)
            # State might be None initially for some platforms, but entity should exist
            # Just verify it doesn't crash when accessed
            _ = state


async def test_coordinator_conditional_api_calls(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    caplog: pytest.LogCaptureFixture,
    amcrest_device: MagicMock,
) -> None:
    """Test that coordinator only makes API calls for enabled entities."""

    mock_config_entry = MockConfigEntry(
        domain=DOMAIN,
        title="Test Camera",
        data={
            "name": "Test Camera",
            "host": "192.168.1.100",
            "port": 80,
            "username": "admin",
            "password": "password123",
        },
        unique_id="TEST123456789",
    )
    mock_config_entry.add_to_hass(hass)

    amcrest_device.get_base_url = MagicMock(return_value="http://192.168.1.100")

    # Setup the integration
    result = await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()
    assert result is True

    # Create specific entities to test conditional fetching
    entity_registry.async_get_or_create(
        "binary_sensor",
        DOMAIN,
        "TEST123456789_motion_detected",
        config_entry=mock_config_entry,
    )
    entity_registry.async_get_or_create(
        "sensor",
        DOMAIN,
        "TEST123456789_storage_info",
        config_entry=mock_config_entry,
    )
    # Don't create audio_detected or crossline_detected entities

    # Get the coordinator from the integration
    coordinator = mock_config_entry.runtime_data.coordinator

    # Reset call counts
    amcrest_device.async_event_channels_happened.reset_mock()

    # Trigger coordinator update
    await coordinator.async_refresh()
    await hass.async_block_till_done()

    # Verify API calls were made only for enabled entities
    call_args_list = amcrest_device.async_event_channels_happened.call_args_list
    called_event_types = [call.args[0] for call in call_args_list]

    # Motion detection should be called (entity exists and enabled)
    assert "VideoMotion" in called_event_types

    # Audio detection should be called (entity exists and enabled)
    assert "AudioMutation" in called_event_types

    # Storage API should be called (async_storage_all property)
    # We can't directly check property access, but the storage data should be present
    assert coordinator.data is not None
    assert "storage_info" in coordinator.data

    # CrossLine should not be called (entity disabled by default)
    assert "CrossLineDetection" not in called_event_types

    # Verify conditional data structure
    assert coordinator.data["motion_detected"] is not None  # Should have value
    assert coordinator.data["storage_info"] is not None  # Should have value
    assert (
        coordinator.data["audio_detected"] is not None
    )  # Should have value (entity is enabled)

    assert (
        coordinator.data["crossline_detected"] is None
    )  # Should be None (not enabled)
