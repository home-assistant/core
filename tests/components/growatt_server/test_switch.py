"""Tests for the Growatt Server switch platform."""

from collections.abc import AsyncGenerator
from unittest.mock import patch

from growattServer import GrowattV1ApiError
import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.switch import DOMAIN as SWITCH_DOMAIN
from homeassistant.const import (
    SERVICE_TURN_OFF,
    SERVICE_TURN_ON,
    STATE_OFF,
    STATE_ON,
    STATE_UNKNOWN,
    EntityCategory,
    Platform,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import entity_registry as er

from tests.common import MockConfigEntry, snapshot_platform


@pytest.fixture(autouse=True)
async def switch_only() -> AsyncGenerator[None]:
    """Enable only the switch platform."""
    with patch(
        "homeassistant.components.growatt_server.PLATFORMS",
        [Platform.SWITCH],
    ):
        yield


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_switch_entities(
    hass: HomeAssistant,
    snapshot: SnapshotAssertion,
    mock_growatt_api,
    mock_get_device_list,
    mock_config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test that switch entities are created for MIN devices."""
    mock_config_entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_switch_entity_values(
    hass: HomeAssistant,
    mock_growatt_api,
    mock_get_device_list,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test that switch entities have correct values."""
    mock_config_entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    # Check entity value (should be ON based on mock data value "1")
    ac_charge_state = hass.states.get("switch.min123456_charge_from_grid")
    assert ac_charge_state is not None
    assert ac_charge_state.state == STATE_ON


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_turn_on_switch_success(
    hass: HomeAssistant,
    mock_growatt_api,
    mock_get_device_list,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test turning on a switch entity successfully."""
    mock_config_entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    await hass.services.async_call(
        SWITCH_DOMAIN,
        SERVICE_TURN_ON,
        {"entity_id": "switch.min123456_charge_from_grid"},
        blocking=True,
    )

    # Verify API was called with correct parameters
    mock_growatt_api.min_write_parameter.assert_called_once_with(
        "MIN123456", "ac_charge", 1
    )


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_turn_off_switch_success(
    hass: HomeAssistant,
    mock_growatt_api,
    mock_get_device_list,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test turning off a switch entity successfully."""
    mock_config_entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    await hass.services.async_call(
        SWITCH_DOMAIN,
        SERVICE_TURN_OFF,
        {"entity_id": "switch.min123456_charge_from_grid"},
        blocking=True,
    )

    # Verify API was called with correct parameters
    mock_growatt_api.min_write_parameter.assert_called_once_with(
        "MIN123456", "ac_charge", 0
    )


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_turn_on_switch_api_error(
    hass: HomeAssistant,
    mock_growatt_api,
    mock_get_device_list,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test handling API error when turning on switch."""
    mock_config_entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    # Mock API to raise error
    mock_growatt_api.min_write_parameter.side_effect = GrowattV1ApiError("API Error")

    with pytest.raises(HomeAssistantError):
        await hass.services.async_call(
            SWITCH_DOMAIN,
            SERVICE_TURN_ON,
            {"entity_id": "switch.min123456_charge_from_grid"},
            blocking=True,
        )


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_turn_off_switch_api_error(
    hass: HomeAssistant,
    mock_growatt_api,
    mock_get_device_list,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test handling API error when turning off switch."""
    mock_config_entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    # Mock API to raise error
    mock_growatt_api.min_write_parameter.side_effect = GrowattV1ApiError("API Error")

    with pytest.raises(HomeAssistantError):
        await hass.services.async_call(
            SWITCH_DOMAIN,
            SERVICE_TURN_OFF,
            {"entity_id": "switch.min123456_charge_from_grid"},
            blocking=True,
        )


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_switch_entity_attributes(
    hass: HomeAssistant,
    mock_growatt_api,
    mock_get_device_list,
    mock_config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test switch entity attributes."""
    mock_config_entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    # Check entity registry attributes
    entity_entry = entity_registry.async_get("switch.min123456_charge_from_grid")
    assert entity_entry is not None
    assert entity_entry.entity_category == EntityCategory.CONFIG
    assert entity_entry.unique_id == "MIN123456_ac_charge"

    # Check state attributes
    state = hass.states.get("switch.min123456_charge_from_grid")
    assert state is not None
    assert state.attributes["friendly_name"] == "MIN123456 Charge from grid"


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_switch_state_handling_integer_values(
    hass: HomeAssistant,
    mock_growatt_api,
    mock_get_device_list,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test switch state handling with integer values from API."""
    # Mock API with integer values (what real API returns)
    mock_growatt_api.min_detail.return_value = {
        "deviceSn": "MIN123456",
        "acChargeEnable": 1,  # Integer value
    }

    mock_config_entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    # Should interpret 1 as ON
    state = hass.states.get("switch.min123456_charge_from_grid")
    assert state is not None
    assert state.state == STATE_ON

    # Test with 0 integer value
    mock_growatt_api.min_detail.return_value = {
        "deviceSn": "MIN123456",
        "acChargeEnable": 0,  # Integer value
    }

    # Trigger a refresh
    runtime_data = mock_config_entry.runtime_data
    device_coordinator = runtime_data.devices["MIN123456"]
    await device_coordinator.async_refresh()

    # Should interpret "0" as OFF
    state = hass.states.get("switch.min123456_charge_from_grid")
    assert state is not None
    assert state.state == STATE_OFF


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_switch_missing_data(
    hass: HomeAssistant,
    mock_growatt_api,
    mock_get_device_list,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test switch entity when coordinator data is missing."""
    # Set up API with missing data for switch entity
    mock_growatt_api.min_detail.return_value = {
        "deviceSn": "MIN123456",
        # Missing 'acChargeEnable' key to test None case
    }

    mock_config_entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    # Entity should exist but have unknown state due to missing data
    state = hass.states.get("switch.min123456_charge_from_grid")
    assert state is not None
    assert state.state == STATE_UNKNOWN


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_no_switch_entities_for_non_min_devices(
    hass: HomeAssistant,
    mock_growatt_api,
    mock_get_device_list,
    mock_config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test that switch entities are not created for non-MIN devices."""
    # Mock a different device type (not MIN)
    mock_get_device_list.return_value = (
        [{"deviceSn": "TLX123456", "deviceType": "tlx"}],
        "12345",
    )

    # Mock TLX API response to prevent coordinator errors
    mock_growatt_api.tlx_detail.return_value = {"data": {}}

    mock_config_entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    # Should have no switch entities for TLX devices
    entity_entries = er.async_entries_for_config_entry(
        entity_registry, mock_config_entry.entry_id
    )
    switch_entities = [entry for entry in entity_entries if entry.domain == "switch"]
    assert len(switch_entities) == 0


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_no_switch_entities_for_non_v1_api(
    hass: HomeAssistant,
    mock_growatt_api,
    mock_get_device_list,
    mock_config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test that switch entities are not created for non-V1 API."""
    # Mock device list to return no MIN devices (since classic API would not support switches)
    mock_get_device_list.return_value = (
        [],  # No devices for classic API in this test
        "12345",
    )

    # Change config entry to use classic API (not V1)
    new_data = {
        "auth_type": "password",  # Classic API
        "username": "test_user",
        "password": "test_password",
        "url": "https://server.growatt.com/",
        "plant_id": "12345",
    }
    mock_config_entry = MockConfigEntry(
        domain="growatt_server",
        data=new_data,
        entry_id=mock_config_entry.entry_id,
    )

    mock_config_entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    # Should have no switch entities for classic API (no devices)
    entity_entries = er.async_entries_for_config_entry(
        entity_registry, mock_config_entry.entry_id
    )
    switch_entities = [entry for entry in entity_entries if entry.domain == "switch"]
    assert len(switch_entities) == 0


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_switch_coordinator_data_update(
    hass: HomeAssistant,
    mock_growatt_api,
    mock_get_device_list,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test that switch state updates when coordinator data changes."""
    mock_config_entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    # Initial state should be ON (based on mock data)
    state = hass.states.get("switch.min123456_charge_from_grid")
    assert state is not None
    assert state.state == STATE_ON

    # Change mock data and trigger coordinator update
    mock_growatt_api.min_detail.return_value = {
        "deviceSn": "MIN123456",
        "acChargeEnable": "0",  # Changed to OFF
    }

    # Trigger a refresh
    runtime_data = mock_config_entry.runtime_data
    device_coordinator = runtime_data.devices["MIN123456"]
    await device_coordinator.async_refresh()

    # State should now be OFF
    state = hass.states.get("switch.min123456_charge_from_grid")
    assert state is not None
    assert state.state == STATE_OFF
