"""Tests for JVC Projector select platform."""

from datetime import timedelta
from unittest.mock import MagicMock

from jvcprojector import command as cmd

from homeassistant.components.jvc_projector.coordinator import INTERVAL_FAST
from homeassistant.components.select import (
    ATTR_OPTIONS,
    DOMAIN as SELECT_DOMAIN,
    SERVICE_SELECT_OPTION,
)
from homeassistant.const import ATTR_ENTITY_ID, ATTR_FRIENDLY_NAME, ATTR_OPTION
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from homeassistant.util.dt import utcnow

from tests.common import MockConfigEntry, async_fire_time_changed

INPUT_ENTITY_ID = "select.jvc_projector_input"
HDR_ENTITY_ID = "select.jvc_projector_hdr"
HDR_PROCESSING_ENTITY_ID = "select.jvc_projector_hdr_processing"


async def test_input_select(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    mock_device: MagicMock,
    mock_integration: MockConfigEntry,
) -> None:
    """Test input select."""
    entity = hass.states.get(INPUT_ENTITY_ID)
    assert entity
    assert entity.attributes.get(ATTR_FRIENDLY_NAME) == "JVC Projector Input"
    assert entity.attributes.get(ATTR_OPTIONS) == [cmd.Input.HDMI1, cmd.Input.HDMI2]

    await hass.services.async_call(
        SELECT_DOMAIN,
        SERVICE_SELECT_OPTION,
        {
            ATTR_ENTITY_ID: INPUT_ENTITY_ID,
            ATTR_OPTION: cmd.Input.HDMI2,
        },
        blocking=True,
    )
    mock_device.set.assert_called_once_with(cmd.Input, cmd.Input.HDMI2)


async def test_enable_hdr_select(
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

    # Allow deferred updates to run (for code coverage)
    async_fire_time_changed(
        hass, utcnow() + timedelta(seconds=INTERVAL_FAST.seconds + 1)
    )
    await hass.async_block_till_done()

    # Allow deferred updates to run again (for code coverage)
    async_fire_time_changed(
        hass, utcnow() + timedelta(seconds=INTERVAL_FAST.seconds + 1)
    )
    await hass.async_block_till_done()
