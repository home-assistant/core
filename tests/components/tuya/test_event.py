"""Test Tuya event platform."""

from __future__ import annotations

from unittest.mock import patch

import pytest
from syrupy.assertion import SnapshotAssertion
from tuya_sharing import CustomerDevice, Manager

from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from . import initialize_entry

from tests.common import MockConfigEntry, snapshot_platform


@patch("homeassistant.components.tuya.PLATFORMS", [Platform.EVENT])
async def test_platform_setup_and_discovery(
    hass: HomeAssistant,
    mock_manager: Manager,
    mock_config_entry: MockConfigEntry,
    mock_devices: list[CustomerDevice],
    entity_registry: er.EntityRegistry,
    snapshot: SnapshotAssertion,
) -> None:
    """Test platform setup and discovery."""
    await initialize_entry(hass, mock_manager, mock_config_entry, mock_devices)

    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)


@pytest.mark.parametrize(
    "mock_device_code",
    ["sp_csr2fqitalj5o0tq"],
)
@patch("homeassistant.components.tuya.PLATFORMS", [Platform.EVENT])
async def test_alarm_message_event(
    hass: HomeAssistant,
    mock_manager: Manager,
    mock_config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
    mock_device: CustomerDevice,
) -> None:
    """Test alarm message event entity triggers correctly."""
    entity_id = "event.intercom_alarm_message"
    dp_code = "alarm_message"

    await initialize_entry(hass, mock_manager, mock_config_entry, mock_device)

    # Verify entity was created
    state = hass.states.get(entity_id)
    assert state is not None

    # Trigger event by calling the entity's update handler directly
    entity = hass.data["entity_components"]["event"].get_entity(entity_id)
    await entity._handle_state_update([dp_code])

    # Verify event was triggered with correct type and decoded message
    state = hass.states.get(entity_id)
    assert state.attributes["event_type"] == "alarm_message"
    assert "ipc_doorbell" in state.attributes["message"]


@pytest.mark.parametrize(
    "mock_device_code",
    ["sp_csr2fqitalj5o0tq"],
)
@patch("homeassistant.components.tuya.PLATFORMS", [Platform.EVENT])
async def test_doorbell_picture_event(
    hass: HomeAssistant,
    mock_manager: Manager,
    mock_config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
    mock_device: CustomerDevice,
) -> None:
    """Test doorbell picture event entity triggers correctly."""
    entity_id = "event.intercom_doorbell_picture"
    dp_code = "doorbell_pic"

    await initialize_entry(hass, mock_manager, mock_config_entry, mock_device)

    # Verify entity was created
    state = hass.states.get(entity_id)
    assert state is not None

    # Trigger event by calling the entity's update handler directly
    entity = hass.data["entity_components"]["event"].get_entity(entity_id)
    await entity._handle_state_update([dp_code])

    # Verify event was triggered with correct type and decoded URL
    state = hass.states.get(entity_id)
    assert state.attributes["event_type"] == "doorbell_pic"
    assert ".jpeg" in state.attributes["picture"]
