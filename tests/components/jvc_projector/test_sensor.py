"""Tests for the JVC Projector binary sensor device."""

from datetime import timedelta
from unittest.mock import MagicMock

from homeassistant.components.jvc_projector.coordinator import INTERVAL_FAST
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from homeassistant.util.dt import utcnow

from tests.common import MockConfigEntry, async_fire_time_changed

POWER_ID = "sensor.jvc_projector_status"
HDR_ENTITY_ID = "sensor.jvc_projector_hdr"
HDR_PROCESSING_ENTITY_ID = "sensor.jvc_projector_hdr_processing"


async def test_entity_state(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    mock_device: MagicMock,
    mock_integration: MockConfigEntry,
) -> None:
    """Tests entity state is registered."""
    state = hass.states.get(POWER_ID)
    assert state
    assert entity_registry.async_get(state.entity_id)
    assert state.state == "on"


async def test_enable_hdr_sensor(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    mock_device,
    mock_integration: MockConfigEntry,
) -> None:
    """Test enabling the HDR select (disabled by default)."""

    # Test entity is disabled initially
    entry = entity_registry.async_get(HDR_ENTITY_ID)
    assert entry is not None
    assert entry.disabled_by is er.RegistryEntryDisabler.INTEGRATION

    # Enable entity
    entity_registry.async_update_entity(HDR_ENTITY_ID, disabled_by=None)
    entity_registry.async_update_entity(HDR_PROCESSING_ENTITY_ID, disabled_by=None)

    # Add to hass
    await hass.config_entries.async_reload(mock_integration.entry_id)
    await hass.async_block_till_done()

    # Verify entity is enabled
    state = hass.states.get(HDR_ENTITY_ID)
    assert state is not None

    # Allow deferred updates to run
    async_fire_time_changed(
        hass, utcnow() + timedelta(seconds=INTERVAL_FAST.seconds + 1)
    )
    await hass.async_block_till_done()

    # Allow deferred updates to run again
    async_fire_time_changed(
        hass, utcnow() + timedelta(seconds=INTERVAL_FAST.seconds + 1)
    )
    await hass.async_block_till_done()

    assert hass.states.get(HDR_PROCESSING_ENTITY_ID) is not None
