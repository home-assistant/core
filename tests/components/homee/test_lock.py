"""Test Homee locks."""

from collections.abc import AsyncGenerator
from unittest.mock import MagicMock, patch

import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.lock import (
    DOMAIN as LOCK_DOMAIN,
    SERVICE_LOCK,
    SERVICE_OPEN,
    SERVICE_UNLOCK,
    LockState,
)
from homeassistant.const import ATTR_ENTITY_ID, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from . import build_mock_node, setup_integration

from tests.common import MockConfigEntry, snapshot_platform


@pytest.fixture(autouse=True)
async def platforms() -> AsyncGenerator[None]:
    """Return the platforms to be loaded for this test."""
    with patch("homeassistant.components.homee.PLATFORMS", [Platform.LOCK]):
        yield


async def setup_lock(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_homee: MagicMock,
    fixture: str = "lock.json",
) -> None:
    """Setups the integration lock tests."""
    mock_homee.nodes = [build_mock_node(fixture)]
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
        blocking=True,
    )
    mock_homee.set_value.assert_called_once_with(1, 1, target_value)


@pytest.mark.parametrize(
    ("fixture", "open_value"),
    [
        ("lock_with_open.json", 2.0),
        ("lock_with_unlatch.json", -1.0),
    ],
)
async def test_lock_open_service(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_homee: MagicMock,
    fixture: str,
    open_value: float,
) -> None:
    """Test the open service on locks that support momentary unlatch.

    Different homee-compatible devices encode the unlatch command
    differently — a positive extension (value 2) or a signed range
    where -1 is unlatch (e.g. the Hörmann SmartKey).
    """
    await setup_lock(hass, mock_config_entry, mock_homee, fixture)

    await hass.services.async_call(
        LOCK_DOMAIN,
        SERVICE_OPEN,
        {ATTR_ENTITY_ID: "lock.test_lock"},
        blocking=True,
    )
    mock_homee.set_value.assert_called_once_with(1, 1, open_value)


@pytest.mark.parametrize(
    ("target_value", "current_value", "expected"),
    [
        (1.0, 1.0, LockState.LOCKED),
        (0.0, 0.0, LockState.UNLOCKED),
        (1.0, 0.0, LockState.LOCKING),
        (0.0, 1.0, LockState.UNLOCKING),
    ],
)
async def test_lock_state(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_homee: MagicMock,
    target_value: float,
    current_value: float,
    expected: LockState,
) -> None:
    """Test lock state."""
    mock_homee.nodes = [build_mock_node("lock.json")]
    mock_homee.get_node_by_id.return_value = mock_homee.nodes[0]
    attribute = mock_homee.nodes[0].attributes[0]
    attribute.target_value = target_value
    attribute.current_value = current_value
    await setup_integration(hass, mock_config_entry)

    assert hass.states.get("lock.test_lock").state == expected


@pytest.mark.parametrize(
    ("fixture", "open_value"),
    [
        ("lock_with_open.json", 2.0),
        ("lock_with_unlatch.json", -1.0),
    ],
)
@pytest.mark.parametrize(
    ("target_offset", "current_offset", "expected"),
    [
        ("open", "open", LockState.OPEN),
        ("open", 0.0, LockState.OPENING),
        ("open", 1.0, LockState.OPENING),
        (1.0, "open", LockState.LOCKING),
        (0.0, "open", LockState.UNLOCKING),
    ],
)
async def test_lock_state_with_open(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_homee: MagicMock,
    fixture: str,
    open_value: float,
    target_offset: float | str,
    current_offset: float | str,
    expected: LockState,
) -> None:
    """Test lock state transitions that involve the open value."""
    mock_homee.nodes = [build_mock_node(fixture)]
    mock_homee.get_node_by_id.return_value = mock_homee.nodes[0]
    attribute = mock_homee.nodes[0].attributes[0]
    attribute.target_value = open_value if target_offset == "open" else target_offset
    attribute.current_value = open_value if current_offset == "open" else current_offset
    await setup_integration(hass, mock_config_entry)

    assert hass.states.get("lock.test_lock").state == expected


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
    mock_homee.nodes = [build_mock_node("lock.json")]
    mock_homee.get_node_by_id.return_value = mock_homee.nodes[0]
    mock_homee.get_user_by_id.return_value = MagicMock(username="testuser")
    attribute = mock_homee.nodes[0].attributes[0]
    attribute.changed_by = attr_changed_by
    attribute.changed_by_id = changed_by_id
    await setup_integration(hass, mock_config_entry)

    assert hass.states.get("lock.test_lock").attributes["changed_by"] == expected


async def test_lock_changed_by_unknown_user(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_homee: MagicMock,
) -> None:
    """Test lock changed by entries."""
    mock_homee.nodes = [build_mock_node("lock.json")]
    mock_homee.get_node_by_id.return_value = mock_homee.nodes[0]
    mock_homee.get_user_by_id.return_value = None  # Simulate unknown user
    attribute = mock_homee.nodes[0].attributes[0]
    attribute.changed_by = 2
    attribute.changed_by_id = 1
    await setup_integration(hass, mock_config_entry)

    assert hass.states.get("lock.test_lock").attributes["changed_by"] == "user-Unknown"


async def test_lock_snapshot(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_homee: MagicMock,
    entity_registry: er.EntityRegistry,
    snapshot: SnapshotAssertion,
) -> None:
    """Test the lock snapshots."""
    await setup_lock(hass, mock_config_entry, mock_homee)

    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)
