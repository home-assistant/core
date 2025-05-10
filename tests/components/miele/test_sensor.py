"""Tests for miele sensor module."""

from unittest.mock import MagicMock

from pymiele import MieleDevices
import pytest
from syrupy import SnapshotAssertion

from homeassistant.components.miele.const import DOMAIN
from homeassistant.components.sensor import DOMAIN as SENSOR_DOMAIN
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from . import get_actions_callback, get_data_callback

from tests.common import MockConfigEntry, load_json_object_fixture, snapshot_platform


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
    device_fixture: MieleDevices,
) -> None:
    """Test sensor state when the API pushes data via SSE."""

    data_callback = get_data_callback(mock_miele_client)
    await data_callback(device_fixture)
    await hass.async_block_till_done()

    act_file = load_json_object_fixture("4_actions.json", DOMAIN)
    action_callback = get_actions_callback(mock_miele_client)
    await action_callback(act_file)
    await hass.async_block_till_done()

    await snapshot_platform(hass, entity_registry, snapshot, setup_platform.entry_id)
