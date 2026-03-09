"""Tests for JVC Projector sensor platform."""

from unittest.mock import MagicMock

from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from tests.common import MockConfigEntry

POWER_ID = "sensor.jvc_projector_status"
HDR_ENTITY_ID = "sensor.jvc_projector_hdr"


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
    """Test enabling the HDR sensor (disabled by default)."""

    # Test entity is disabled initially
    entry = entity_registry.async_get(HDR_ENTITY_ID)
    assert entry is not None
    assert entry.disabled_by is er.RegistryEntryDisabler.INTEGRATION

    # Enable entity
    entity_registry.async_update_entity(HDR_ENTITY_ID, disabled_by=None)
    # Add to hass
    await hass.config_entries.async_reload(mock_integration.entry_id)
    await hass.async_block_till_done()

    # Verify entity is enabled
    state = hass.states.get(HDR_ENTITY_ID)
    assert state is not None
