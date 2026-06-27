"""Tests for the KEBA charging station lock platform."""

from unittest.mock import MagicMock

import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.lock import DOMAIN as LOCK_DOMAIN
from homeassistant.const import SERVICE_LOCK, SERVICE_UNLOCK
from homeassistant.core import HomeAssistant

LOCK_ENTITY_ID = "lock.kc_p30_authentication"


@pytest.mark.usefixtures("init_integration")
async def test_lock_entity_created(hass: HomeAssistant) -> None:
    """Test that the lock entity is created."""
    assert hass.states.get(LOCK_ENTITY_ID) is not None


@pytest.mark.usefixtures("init_integration")
async def test_lock_state(
    hass: HomeAssistant,
    snapshot: SnapshotAssertion,
) -> None:
    """Test the lock state matches snapshot."""
    assert hass.states.get(LOCK_ENTITY_ID) == snapshot


@pytest.mark.usefixtures("init_integration")
async def test_lock_lock(
    hass: HomeAssistant,
    mock_keba: MagicMock,
) -> None:
    """Test that locking calls async_stop."""
    await hass.services.async_call(
        LOCK_DOMAIN,
        SERVICE_LOCK,
        {"entity_id": LOCK_ENTITY_ID},
        blocking=True,
    )
    mock_keba.async_stop.assert_called_once()


@pytest.mark.usefixtures("init_integration")
async def test_lock_unlock(
    hass: HomeAssistant,
    mock_keba: MagicMock,
) -> None:
    """Test that unlocking calls async_start."""
    await hass.services.async_call(
        LOCK_DOMAIN,
        SERVICE_UNLOCK,
        {"entity_id": LOCK_ENTITY_ID},
        blocking=True,
    )
    mock_keba.async_start.assert_called_once()
