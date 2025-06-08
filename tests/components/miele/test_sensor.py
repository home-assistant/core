"""Tests for miele sensor module."""

from unittest.mock import MagicMock

import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.sensor import DOMAIN as SENSOR_DOMAIN
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from tests.common import MockConfigEntry, snapshot_platform


@pytest.mark.parametrize("platforms", [(SENSOR_DOMAIN,)])
@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_sensor_states(
    hass: HomeAssistant,
    mock_miele_client: MagicMock,
    snapshot: SnapshotAssertion,
    entity_registry: er.EntityRegistry,
    setup_platform: MockConfigEntry,
) -> None:
    """Test sensor state after polling the API for data."""

    await snapshot_platform(hass, entity_registry, snapshot, setup_platform.entry_id)


@pytest.mark.parametrize("platforms", [(SENSOR_DOMAIN,)])
@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_sensor_states_api_push(
    hass: HomeAssistant,
    mock_miele_client: MagicMock,
    snapshot: SnapshotAssertion,
    entity_registry: er.EntityRegistry,
    setup_platform: MockConfigEntry,
    push_data_and_actions: None,
) -> None:
    """Test sensor state when the API pushes data via SSE."""

    await snapshot_platform(hass, entity_registry, snapshot, setup_platform.entry_id)


@pytest.mark.parametrize("load_device_file", ["hob.json"])
@pytest.mark.parametrize("platforms", [(SENSOR_DOMAIN,)])
@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_hob_sensor_states(
    hass: HomeAssistant,
    mock_miele_client: MagicMock,
    snapshot: SnapshotAssertion,
    entity_registry: er.EntityRegistry,
    setup_platform: None,
) -> None:
    """Test sensor state."""

    await snapshot_platform(hass, entity_registry, snapshot, setup_platform.entry_id)
