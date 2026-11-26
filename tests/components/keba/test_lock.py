"""Tests for the KEBA charging station authentication lock."""

from typing import Any
from unittest.mock import MagicMock

from freezegun.api import FrozenDateTimeFactory
import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.lock import DOMAIN as LOCK_DOMAIN, LockService, LockState
from homeassistant.const import TargetKey
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from .conftest import async_advance, async_seconds_until_poll, async_settle

ENTITY_ID = "lock.keba_p30_authentication"

pytestmark = pytest.mark.usefixtures("setup_keba")


async def test_lock(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    snapshot: SnapshotAssertion,
) -> None:
    """Test the lock entity, its unique ID and state."""
    assert entity_registry.async_get(ENTITY_ID) == snapshot(name="entry")
    assert hass.states.get(ENTITY_ID) == snapshot(name="state")


@pytest.mark.parametrize(
    ("authreq", "expected"),
    [(0, LockState.UNLOCKED), (1, LockState.LOCKED)],
)
async def test_lock_follows_authreq(
    hass: HomeAssistant,
    keba_data: dict[str, Any],
    freezer: FrozenDateTimeFactory,
    authreq: int,
    expected: LockState,
) -> None:
    """Test the lock is locked while the station requires authorization."""
    keba_data["Authreq"] = authreq

    await async_advance(hass, freezer, 5)

    assert hass.states.get(ENTITY_ID).state == expected


@pytest.mark.parametrize(
    ("service", "command"),
    [(LockService.LOCK, "stop"), (LockService.UNLOCK, "start")],
)
async def test_lock_commands(
    hass: HomeAssistant,
    setup_keba: MagicMock,
    freezer: FrozenDateTimeFactory,
    service: LockService,
    command: str,
) -> None:
    """Test locking deauthorizes and unlocking authorizes, then polls faster."""
    await hass.services.async_call(
        LOCK_DOMAIN, service, {TargetKey.ENTITY_ID: ENTITY_ID}, blocking=True
    )
    await async_settle(hass)

    getattr(setup_keba, command).assert_awaited_once_with("00845500")
    assert await async_seconds_until_poll(hass, freezer, setup_keba) == 2
