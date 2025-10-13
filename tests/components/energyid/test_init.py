"""Tests for EnergyID integration initialization."""

from unittest.mock import ANY, MagicMock

from homeassistant.components.energyid.const import (
    CONF_ENERGYID_KEY,
    CONF_HA_ENTITY_UUID,
)
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import STATE_UNAVAILABLE, STATE_UNKNOWN
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers import entity_registry as er

from tests.common import MockConfigEntry


async def test_successful_setup(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_webhook_client: MagicMock,
) -> None:
    """Test the integration sets up successfully."""
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.LOADED
    mock_webhook_client.authenticate.assert_called_once()


async def test_setup_retries_on_timeout(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_webhook_client: MagicMock,
) -> None:
    """Test setup retries when there is a connection timeout."""
    mock_webhook_client.authenticate.side_effect = ConfigEntryNotReady

    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.SETUP_RETRY


async def test_setup_fails_on_auth_error(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_webhook_client: MagicMock,
) -> None:
    """Test setup fails when authentication returns an unexpected error."""
    mock_webhook_client.authenticate.side_effect = Exception("Unexpected error")

    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.SETUP_ERROR


async def test_setup_fails_when_not_claimed(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_webhook_client: MagicMock,
) -> None:
    """Test setup fails when device is not claimed."""
    mock_webhook_client.authenticate.return_value = False

    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.SETUP_ERROR


async def test_state_change_sends_data(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_webhook_client: MagicMock,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test that a sensor state change is correctly sent to the EnergyID API."""
    # ARRANGE: Prepare the config entry with sub-entries BEFORE setup.
    entity_entry = entity_registry.async_get_or_create(
        "sensor", "test_platform", "power_1", suggested_object_id="power_meter"
    )
    hass.states.async_set(entity_entry.entity_id, STATE_UNAVAILABLE)
    sub_entry = {
        "data": {CONF_HA_ENTITY_UUID: entity_entry.id, CONF_ENERGYID_KEY: "grid_power"}
    }
    mock_config_entry.subentries = {"sub_entry_1": MagicMock(**sub_entry)}

    # ACT 1: Set up the integration.
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    # ACT 2: Simulate the sensor reporting a new value.
    hass.states.async_set(entity_entry.entity_id, "123.45")
    await hass.async_block_till_done()

    # ASSERT
    mock_webhook_client.get_or_create_sensor.assert_called_with("grid_power")
    sensor_mock = mock_webhook_client.get_or_create_sensor.return_value
    sensor_mock.update.assert_called_once_with(123.45, ANY)


async def test_state_change_handles_invalid_values(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_webhook_client: MagicMock,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test that invalid state values are handled gracefully."""
    entity_entry = entity_registry.async_get_or_create(
        "sensor", "test_platform", "power_2", suggested_object_id="invalid_sensor"
    )
    hass.states.async_set(entity_entry.entity_id, STATE_UNAVAILABLE)
    sub_entry = {
        "data": {CONF_HA_ENTITY_UUID: entity_entry.id, CONF_ENERGYID_KEY: "grid_power"}
    }
    mock_config_entry.subentries = {"sub_entry_1": MagicMock(**sub_entry)}

    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    # Reset the mock to clear any calls from setup
    sensor_mock = mock_webhook_client.get_or_create_sensor.return_value
    sensor_mock.update.reset_mock()

    # Act: Send an invalid (non-numeric) value
    hass.states.async_set(entity_entry.entity_id, "invalid")
    await hass.async_block_till_done()

    # ASSERT: No sensor update call should happen for invalid values
    sensor_mock.update.assert_not_called()


async def test_state_change_ignores_unavailable(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_webhook_client: MagicMock,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test that unavailable states are ignored."""
    entity_entry = entity_registry.async_get_or_create(
        "sensor", "test_platform", "power_3", suggested_object_id="unavailable_sensor"
    )
    hass.states.async_set(entity_entry.entity_id, "100")
    sub_entry = {
        "data": {CONF_HA_ENTITY_UUID: entity_entry.id, CONF_ENERGYID_KEY: "grid_power"}
    }
    mock_config_entry.subentries = {"sub_entry_1": MagicMock(**sub_entry)}

    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    # Reset the mock
    sensor_mock = mock_webhook_client.get_or_create_sensor.return_value
    sensor_mock.update.reset_mock()

    # Act: Set to unavailable
    hass.states.async_set(entity_entry.entity_id, STATE_UNAVAILABLE)
    await hass.async_block_till_done()

    # ASSERT: No update for unavailable state
    sensor_mock.update.assert_not_called()


async def test_state_change_ignores_unknown(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_webhook_client: MagicMock,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test that unknown states are ignored."""
    entity_entry = entity_registry.async_get_or_create(
        "sensor", "test_platform", "power_4", suggested_object_id="unknown_sensor"
    )
    hass.states.async_set(entity_entry.entity_id, "100")
    sub_entry = {
        "data": {CONF_HA_ENTITY_UUID: entity_entry.id, CONF_ENERGYID_KEY: "grid_power"}
    }
    mock_config_entry.subentries = {"sub_entry_1": MagicMock(**sub_entry)}

    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    # Reset the mock
    sensor_mock = mock_webhook_client.get_or_create_sensor.return_value
    sensor_mock.update.reset_mock()

    # Act: Set to unknown
    hass.states.async_set(entity_entry.entity_id, STATE_UNKNOWN)
    await hass.async_block_till_done()

    # ASSERT: No update for unknown state
    sensor_mock.update.assert_not_called()


async def test_listener_tracks_entity_rename(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_webhook_client: MagicMock,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test that the integration correctly handles a mapped entity being renamed."""
    # ARRANGE: Prepare the config entry with sub-entries BEFORE setup.
    entity_entry = entity_registry.async_get_or_create(
        "sensor", "test_platform", "power_5", suggested_object_id="power_meter"
    )
    hass.states.async_set(entity_entry.entity_id, "50")
    sub_entry = {
        "data": {CONF_HA_ENTITY_UUID: entity_entry.id, CONF_ENERGYID_KEY: "grid_power"}
    }
    mock_config_entry.subentries = {"sub_entry_1": MagicMock(**sub_entry)}

    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    # Reset the mock to clear calls from setup
    sensor_mock = mock_webhook_client.get_or_create_sensor.return_value
    sensor_mock.update.reset_mock()

    # ACT 1: Rename the entity in registry first, then set state for new entity_id
    # This avoids the "Entity with this ID is already registered" error
    new_entity_id = "sensor.new_and_improved_power_meter"
    old_state = hass.states.get(entity_entry.entity_id)
    entity_registry.async_update_entity(
        entity_entry.entity_id, new_entity_id=new_entity_id
    )
    # Set state for new entity_id after rename to simulate migration
    hass.states.async_set(new_entity_id, old_state.state)
    # Clear old state to simulate HA's actual rename behavior
    hass.states.async_set(entity_entry.entity_id, None)
    await hass.async_block_till_done()

    # Reset again after the rename triggers update_listeners
    sensor_mock.update.reset_mock()

    # ACT 2: Post a new value to the renamed entity
    hass.states.async_set(new_entity_id, "1000")
    await hass.async_block_till_done()

    # ASSERT: The listener should track the new entity ID
    sensor_mock.update.assert_called_with(1000.0, ANY)


async def test_listener_tracks_entity_removal(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_webhook_client: MagicMock,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test that the integration handles entity removal."""
    entity_entry = entity_registry.async_get_or_create(
        "sensor", "test_platform", "power_6", suggested_object_id="removable_meter"
    )
    hass.states.async_set(entity_entry.entity_id, "100")
    sub_entry = {
        "data": {CONF_HA_ENTITY_UUID: entity_entry.id, CONF_ENERGYID_KEY: "grid_power"}
    }
    mock_config_entry.subentries = {"sub_entry_1": MagicMock(**sub_entry)}

    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    # ACT: Remove the entity
    entity_registry.async_remove(entity_entry.entity_id)
    await hass.async_block_till_done()

    # ASSERT: Integration should still be loaded (just no longer tracking that entity)
    assert mock_config_entry.state is ConfigEntryState.LOADED


async def test_entity_not_in_state_machine_during_setup(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_webhook_client: MagicMock,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test entity that exists in registry but not state machine during setup."""
    entity_entry = entity_registry.async_get_or_create(
        "sensor", "test_platform", "power_7", suggested_object_id="ghost_meter"
    )
    # Note: NOT setting a state for this entity initially
    sub_entry = {
        "data": {CONF_HA_ENTITY_UUID: entity_entry.id, CONF_ENERGYID_KEY: "grid_power"}
    }
    mock_config_entry.subentries = {"sub_entry_1": MagicMock(**sub_entry)}

    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    # ASSERT: Should still load successfully
    assert mock_config_entry.state is ConfigEntryState.LOADED

    # Reset mock to clear any setup calls
    sensor_mock = mock_webhook_client.get_or_create_sensor.return_value
    sensor_mock.update.reset_mock()

    # Now add the state - entity should be tracked dynamically
    hass.states.async_set(entity_entry.entity_id, "200")
    await hass.async_block_till_done()

    # ASSERT: Entity should now be tracked and update called
    sensor_mock.update.assert_called_with(200.0, ANY)


async def test_unload_cleans_up_listeners(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_webhook_client: MagicMock,
) -> None:
    """Test unloading the integration cleans up properly."""
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    # ACT: Unload the integration
    result = await hass.config_entries.async_unload(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    # ASSERT: Unload was successful
    assert result is True
    assert mock_config_entry.state is ConfigEntryState.NOT_LOADED
    mock_webhook_client.close.assert_called_once()


async def test_no_valid_subentries_setup(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_webhook_client: MagicMock,
) -> None:
    """Test setup with no valid subentries completes successfully."""
    # Set up empty subentries
    mock_config_entry.subentries = {}

    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    # ASSERT: Still loads successfully but with no mappings
    assert mock_config_entry.state is ConfigEntryState.LOADED
    mock_webhook_client.authenticate.assert_called_once()


async def test_subentry_with_missing_uuid(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_webhook_client: MagicMock,
) -> None:
    """Test subentry with missing entity UUID is skipped."""
    sub_entry = {
        "data": {CONF_ENERGYID_KEY: "grid_power"}  # Missing CONF_HA_ENTITY_UUID
    }
    mock_config_entry.subentries = {"sub_entry_1": MagicMock(**sub_entry)}

    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    # ASSERT: Still loads successfully
    assert mock_config_entry.state is ConfigEntryState.LOADED


async def test_subentry_with_nonexistent_entity(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_webhook_client: MagicMock,
) -> None:
    """Test subentry referencing non-existent entity UUID."""
    sub_entry = {
        "data": {
            CONF_HA_ENTITY_UUID: "nonexistent-uuid-12345",
            CONF_ENERGYID_KEY: "grid_power",
        }
    }
    mock_config_entry.subentries = {"sub_entry_1": MagicMock(**sub_entry)}

    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    # ASSERT: Still loads successfully (entity is just skipped with warning)
    assert mock_config_entry.state is ConfigEntryState.LOADED


async def test_initial_state_queued_for_new_mapping(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_webhook_client: MagicMock,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test that initial state is queued when a new mapping is detected."""
    entity_entry = entity_registry.async_get_or_create(
        "sensor", "test_platform", "power_8", suggested_object_id="initial_meter"
    )
    hass.states.async_set(entity_entry.entity_id, "42.5")
    sub_entry = {
        "data": {CONF_HA_ENTITY_UUID: entity_entry.id, CONF_ENERGYID_KEY: "grid_power"}
    }
    mock_config_entry.subentries = {"sub_entry_1": MagicMock(**sub_entry)}

    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    # ASSERT: Initial state should have been sent
    sensor_mock = mock_webhook_client.get_or_create_sensor.return_value
    sensor_mock.update.assert_called_with(42.5, ANY)


async def test_synchronize_sensors_error_handling(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_webhook_client: MagicMock,
) -> None:
    """Test that synchronize_sensors errors are handled gracefully."""
    mock_webhook_client.synchronize_sensors.side_effect = OSError("Connection failed")

    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    # ASSERT: Integration should still load
    assert mock_config_entry.state is ConfigEntryState.LOADED


async def test_config_entry_update_listener(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_webhook_client: MagicMock,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test that config entry update listener reloads listeners."""
    entity_entry = entity_registry.async_get_or_create(
        "sensor", "test_platform", "power_9", suggested_object_id="update_meter"
    )
    hass.states.async_set(entity_entry.entity_id, "100")
    sub_entry = {
        "data": {CONF_HA_ENTITY_UUID: entity_entry.id, CONF_ENERGYID_KEY: "grid_power"}
    }
    mock_config_entry.subentries = {"sub_entry_1": MagicMock(**sub_entry)}

    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    # Reset mock
    sensor_mock = mock_webhook_client.get_or_create_sensor.return_value
    sensor_mock.update.reset_mock()

    # Add a new subentry dynamically
    entity_entry2 = entity_registry.async_get_or_create(
        "sensor", "test_platform", "power_10", suggested_object_id="second_meter"
    )
    hass.states.async_set(entity_entry2.entity_id, "200")
    sub_entry2 = {
        "data": {
            CONF_HA_ENTITY_UUID: entity_entry2.id,
            CONF_ENERGYID_KEY: "solar_power",
        }
    }
    mock_config_entry.subentries["sub_entry_2"] = MagicMock(**sub_entry2)

    # Trigger update listener
    await hass.config_entries.async_reload(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    # ASSERT: Integration reloaded successfully
    assert mock_config_entry.state is ConfigEntryState.LOADED
