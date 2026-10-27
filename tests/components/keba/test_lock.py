"""Tests for the KEBA charging station authentication lock."""

from typing import Any
from unittest.mock import MagicMock

from freezegun.api import FrozenDateTimeFactory
import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.lock import (
    DOMAIN as LOCK_DOMAIN,
    SERVICE_LOCK,
    SERVICE_UNLOCK,
    LockState,
)
from homeassistant.const import ATTR_ENTITY_ID, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from . import snapshot_keba_platform
from .conftest import (
    POLL_INTERVAL,
    async_advance,
    async_seconds_until_poll,
    async_settle,
)

ENTITY_ID = "lock.keba_p30_authentication"


async def test_lock(
    hass: HomeAssistant,
    setup_keba: MagicMock,
    entity_registry: er.EntityRegistry,
    snapshot: SnapshotAssertion,
) -> None:
    """Test the lock entity, its unique ID and state."""
    snapshot_keba_platform(hass, entity_registry, snapshot, Platform.LOCK)


@pytest.mark.parametrize(
    ("authreq", "expected"),
    [(0, LockState.UNLOCKED), (1, LockState.LOCKED)],
)
async def test_lock_follows_authreq(
    hass: HomeAssistant,
    setup_keba: MagicMock,
    keba_data: dict[str, Any],
    freezer: FrozenDateTimeFactory,
    authreq: int,
    expected: LockState,
) -> None:
    """Test the lock is locked while the station requires authorization."""
    keba_data["Authreq"] = authreq

    await async_advance(hass, freezer, POLL_INTERVAL)

    assert hass.states.get(ENTITY_ID).state == expected


@pytest.mark.parametrize(
    ("service", "command"),
    [(SERVICE_LOCK, "stop"), (SERVICE_UNLOCK, "start")],
)
async def test_lock_commands(
    hass: HomeAssistant,
    setup_keba: MagicMock,
    freezer: FrozenDateTimeFactory,
    service: str,
    command: str,
) -> None:
    """Test locking deauthorizes and unlocking authorizes, with fast polling."""
    await hass.services.async_call(
        LOCK_DOMAIN, service, {ATTR_ENTITY_ID: ENTITY_ID}, blocking=True
    )
    await async_settle(hass)

    getattr(setup_keba, command).assert_awaited_once_with("00845500")
    assert await async_seconds_until_poll(hass, freezer, setup_keba) == 2
