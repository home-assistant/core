"""Test Flow-it binary sensor platform."""

from unittest.mock import AsyncMock, patch

from syrupy.assertion import SnapshotAssertion

from homeassistant.components.flow_it.coordinator import FlowItCoordinator
from homeassistant.const import STATE_OFF, STATE_ON, STATE_UNKNOWN, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from tests.common import MockConfigEntry, snapshot_platform

BYPASS_ENTITY_ID = "binary_sensor.001122334455_bypass_active"
CONDENSATION_ENTITY_ID = "binary_sensor.001122334455_condensation_alert"
ICE_ENTITY_ID = "binary_sensor.001122334455_ice_alert"
SERVICE_ENTITY_ID = "binary_sensor.001122334455_service_required"
UPDATE_REBOOT_ENTITY_ID = "binary_sensor.001122334455_update_reboot_pending"
WARMUP_ENTITY_ID = "binary_sensor.001122334455_warmup_mode"
WORRIES_ENTITY_ID = "binary_sensor.001122334455_general_issue"


async def test_binary_sensor_setup(
    hass: HomeAssistant,
    mock_flow_it: AsyncMock,
    mock_config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
    snapshot: SnapshotAssertion,
) -> None:
    """Test binary sensor platform setup and entity registry."""
    with patch("homeassistant.components.flow_it.PLATFORMS", [Platform.BINARY_SENSOR]):
        assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

        disabled_entries = [
            entity_entry
            for entity_entry in er.async_entries_for_config_entry(
                entity_registry, mock_config_entry.entry_id
            )
            if entity_entry.disabled_by is not None
        ]
        assert len(disabled_entries) == 1
        assert disabled_entries[0].entity_id == WARMUP_ENTITY_ID
        assert disabled_entries[0].disabled_by is er.RegistryEntryDisabler.INTEGRATION

        for entity_entry in disabled_entries:
            entity_registry.async_update_entity(
                entity_entry.entity_id, disabled_by=None
            )

        await hass.config_entries.async_reload(mock_config_entry.entry_id)
        await hass.async_block_till_done()

        await snapshot_platform(
            hass, entity_registry, snapshot, mock_config_entry.entry_id
        )


async def test_binary_sensor_none_values(
    hass: HomeAssistant,
    mock_flow_it: AsyncMock,
    mock_config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test binary sensor state when values are None."""
    mock_flow_it.return_value.state.data.alert.ice = None
    mock_flow_it.return_value.state.data.alert.condensation = None
    mock_flow_it.return_value.state.data.alert.service = None
    mock_flow_it.return_value.state.data.alert.worries = None
    mock_flow_it.return_value.state.data.alert.update_reboot = None
    mock_flow_it.return_value.state.data.alert.warmup = None
    mock_flow_it.return_value.state.data.mode.bypassOn = None

    with patch("homeassistant.components.flow_it.PLATFORMS", [Platform.BINARY_SENSOR]):
        assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

        entity_registry.async_update_entity(WARMUP_ENTITY_ID, disabled_by=None)
        await hass.config_entries.async_reload(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    for entity_id in (
        ICE_ENTITY_ID,
        CONDENSATION_ENTITY_ID,
        SERVICE_ENTITY_ID,
        WORRIES_ENTITY_ID,
        UPDATE_REBOOT_ENTITY_ID,
        BYPASS_ENTITY_ID,
        WARMUP_ENTITY_ID,
    ):
        state = hass.states.get(entity_id)
        assert state
        assert state.state == STATE_UNKNOWN


async def test_binary_sensor_update(
    hass: HomeAssistant,
    mock_flow_it: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test binary sensor state updates via coordinator."""
    with patch("homeassistant.components.flow_it.PLATFORMS", [Platform.BINARY_SENSOR]):
        assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    state = hass.states.get(ICE_ENTITY_ID)
    assert state
    assert state.state == STATE_OFF

    state = hass.states.get(BYPASS_ENTITY_ID)
    assert state
    assert state.state == STATE_OFF

    mock_flow_it.return_value.state.data.alert.ice = True
    mock_flow_it.return_value.state.data.mode.bypassOn = True
    coordinator: FlowItCoordinator = mock_config_entry.runtime_data.coordinator
    await coordinator.async_refresh()
    await hass.async_block_till_done()

    state = hass.states.get(ICE_ENTITY_ID)
    assert state
    assert state.state == STATE_ON

    state = hass.states.get(BYPASS_ENTITY_ID)
    assert state
    assert state.state == STATE_ON
