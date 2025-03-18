"""Test Homee locks."""

from unittest.mock import MagicMock, patch

import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.lock import (
    DOMAIN as LOCK_DOMAIN,
    SERVICE_LOCK,
    SERVICE_UNLOCK,
)
from homeassistant.const import ATTR_ENTITY_ID, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from . import build_mock_node, setup_integration

from tests.common import MockConfigEntry, snapshot_platform


async def setup_lock(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry, mock_homee: MagicMock
) -> None:
    """Setups the integration lock tests."""
    mock_homee.nodes = [build_mock_node("lock.json")]
    mock_homee.get_node_by_id.return_value = mock_homee.nodes[0]
    await setup_integration(hass, mock_config_entry)


@pytest.mark.parametrize(
    ("service", "target_value"),
    [
        (SERVICE_LOCK, 1),
        (SERVICE_UNLOCK, 0),
    ],
)
async def test_lock_services(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_homee: MagicMock,
    service: str,
    target_value: int,
) -> None:
    """Test lock services."""
    await setup_lock(hass, mock_config_entry, mock_homee)

    await hass.services.async_call(
        LOCK_DOMAIN,
        service,
        {ATTR_ENTITY_ID: "lock.test_lock"},
    )
    mock_homee.set_value.assert_called_once_with(1, 1, target_value)


@pytest.mark.parametrize(
    ("attr_changed_by", "changed_by_id", "expected"),
    [
        (1, 0, "itself-0"),
        (2, 1, "user-testuser"),
        (3, 54, "homeegram-54"),
        (6, 0, "ai-0"),
    ],
)
async def test_lock_changed_by(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_homee: MagicMock,
    attr_changed_by: int,
    changed_by_id: int,
    expected: str,
) -> None:
    """Test lock changed by entries."""
    await setup_lock(hass, mock_config_entry, mock_homee)
    mock_homee.get_user_by_id.return_value = MagicMock(username="testuser")

    attribute = mock_homee.nodes[0].attributes[0]
    attribute.changed_by = attr_changed_by
    attribute.changed_by_id = changed_by_id
    attribute.add_on_changed_listener.call_args_list[0][0][0](attribute)
    await hass.async_block_till_done()

    assert hass.states.get("lock.test_lock").attributes["changed_by"] == expected


async def test_lock_snapshot(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_homee: MagicMock,
    entity_registry: er.EntityRegistry,
    snapshot: SnapshotAssertion,
) -> None:
    """Test the lock snapshots."""
    with patch("homeassistant.components.homee.PLATFORMS", [Platform.LOCK]):
        await setup_lock(hass, mock_config_entry, mock_homee)

    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)
