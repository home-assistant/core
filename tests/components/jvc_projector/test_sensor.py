"""Tests for the JVC Projector binary sensor device."""

from unittest.mock import MagicMock, patch

import pytest
from syrupy import SnapshotAssertion

from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from . import setup_integration

from tests.common import MockConfigEntry, snapshot_platform


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_entity_state(
    hass: HomeAssistant,
    snapshot: SnapshotAssertion,
    entity_registry: er.EntityRegistry,
    mock_device: MagicMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Tests entity state is registered."""
    with patch("homeassistant.components.jvc_projector.PLATFORMS", [Platform.SENSOR]):
        await setup_integration(hass, mock_config_entry)

    # use a snapshot to validate state of entities
    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)


async def test_disabled_entity(
    hass: HomeAssistant,
    snapshot: SnapshotAssertion,
    entity_registry: er.EntityRegistry,
    mock_device: MagicMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Tests entity is disabled by default."""
    with patch("homeassistant.components.jvc_projector.PLATFORMS", [Platform.SENSOR]):
        await setup_integration(hass, mock_config_entry)
    DISABLED_ID = "sensor.jvc_projector_color_space"

    assert hass.states.get(DISABLED_ID) is None

    # Entity should exist in registry but be disabled
    entity = entity_registry.async_get(DISABLED_ID)
    assert entity
    assert entity.disabled
    assert entity.entity_category == "diagnostic"
