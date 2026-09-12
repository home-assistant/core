"""Tests for JVC Projector sensor platform."""

from unittest.mock import MagicMock

from jvcprojector import Command, command as cmd
import pytest

from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from tests.common import MockConfigEntry

POWER_ID = "sensor.jvc_projector_status"
HDR_ENTITY_ID = "sensor.jvc_projector_hdr"


@pytest.mark.parametrize(
    ("entity_id", "expected_state"),
    [
        ("sensor.jvc_projector_resolution", "4k"),
        ("sensor.jvc_projector_colorimetry", "bt-709"),
        ("sensor.jvc_projector_link_rate", "6-gbps-4-lanes"),
    ],
)
async def test_diagnostic_sensor_state(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    mock_device: MagicMock,
    mock_integration: MockConfigEntry,
    entity_id: str,
    expected_state: str,
) -> None:
    """Test diagnostic sensor state and disabled-by-default behavior."""
    entry = entity_registry.async_get(entity_id)
    assert entry is not None
    assert entry.disabled_by is er.RegistryEntryDisabler.INTEGRATION

    entity_registry.async_update_entity(entity_id, disabled_by=None)
    await hass.config_entries.async_reload(mock_integration.entry_id)
    await hass.async_block_till_done()

    state = hass.states.get(entity_id)
    assert state is not None
    assert state.state == expected_state


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


@pytest.mark.parametrize(
    ("unsupported_command", "entity_id"),
    [
        (cmd.Source, "sensor.jvc_projector_resolution"),
        (cmd.Colorimetry, "sensor.jvc_projector_colorimetry"),
        (cmd.LinkRate, "sensor.jvc_projector_link_rate"),
    ],
)
async def test_unsupported_sensor_not_added(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    mock_device: MagicMock,
    mock_config_entry: MockConfigEntry,
    unsupported_command: type[Command],
    entity_id: str,
) -> None:
    """Test unsupported sensor descriptions are skipped."""
    mock_device.supports.side_effect = lambda command: command is not unsupported_command

    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert entity_registry.async_get(entity_id) is None
