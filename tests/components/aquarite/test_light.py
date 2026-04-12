"""Tests for AquariteLightEntity reconciliation logic."""

from __future__ import annotations

import time
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from homeassistant.components.aquarite.light import (
    RECONCILIATION_TIMEOUT,
    AquariteLightEntity,
)

from .conftest import MOCK_POOL_ID, MOCK_POOL_NAME


def _make_coordinator(light_status: int = 0) -> MagicMock:
    """Build a mock coordinator with configurable light status."""

    data: dict[str, Any] = {"light": {"status": light_status}}

    def _get_value(path: str, default: Any = None) -> Any:
        keys = path.split(".")
        current: Any = data
        for key in keys:
            if isinstance(current, dict) and key in current:
                current = current[key]
            else:
                return default
        return current

    coord = MagicMock()
    coord.data = data
    coord.pool_id = MOCK_POOL_ID
    coord.get_value = MagicMock(side_effect=_get_value)
    coord.api = MagicMock()
    coord.api.set_value = AsyncMock()
    return coord


def _patch_entity_init():
    """Patch CoordinatorEntity.__init__ to skip hass wiring."""
    return patch(
        "homeassistant.helpers.update_coordinator.CoordinatorEntity.__init__",
        lambda self, coordinator, context=None: setattr(
            self, "coordinator", coordinator
        ),
    )


def _make_light(light_status: int = 0) -> tuple[AquariteLightEntity, MagicMock]:
    """Create a light entity with a mocked coordinator."""
    coord = _make_coordinator(light_status)
    with _patch_entity_init():
        entity = AquariteLightEntity(
            coord, MOCK_POOL_ID, MOCK_POOL_NAME, "pool_light", "light.status"
        )
    # Stub async_write_ha_state since there's no hass
    entity.async_write_ha_state = MagicMock()
    return entity, coord


# ── Basic state tests ────────────────────────────────────────────


def test_is_on_returns_false_when_off() -> None:
    """Test is_on returns False when light status is 0."""
    entity, _ = _make_light(0)
    assert entity.is_on is False


def test_is_on_returns_true_when_on() -> None:
    """Test is_on returns True when light status is 1."""
    entity, _ = _make_light(1)
    assert entity.is_on is True


# ── Optimistic state after _send_command ─────────────────────────


@pytest.mark.asyncio
async def test_optimistic_state_after_turn_on() -> None:
    """Test is_on returns True optimistically after turn_on, even if cloud still says 0."""
    entity, coord = _make_light(0)

    await entity.async_turn_on()

    # Cloud still reports 0, but entity should be optimistic
    assert entity._target_state is True
    assert entity.is_on is True
    coord.api.set_value.assert_awaited_once_with(
        MOCK_POOL_ID, "light.status", 1
    )


@pytest.mark.asyncio
async def test_optimistic_state_after_turn_off() -> None:
    """Test is_on returns False optimistically after turn_off, even if cloud still says 1."""
    entity, coord = _make_light(1)

    await entity.async_turn_off()

    # Cloud still reports 1, but entity should be optimistic
    assert entity._target_state is False
    assert entity.is_on is False
    coord.api.set_value.assert_awaited_once_with(
        MOCK_POOL_ID, "light.status", 0
    )


# ── Cloud matches target → clears optimistic state ──────────────


@pytest.mark.asyncio
async def test_clears_optimistic_when_cloud_matches() -> None:
    """Test _target_state is cleared when cloud data matches the target."""
    entity, coord = _make_light(0)

    await entity.async_turn_on()
    assert entity._target_state is True

    # Simulate cloud catching up: update coordinator data to 1
    coord.data["light"]["status"] = 1

    assert entity.is_on is True
    # _target_state should be cleared since cloud now matches
    assert entity._target_state is None


# ── Timeout reverts to actual cloud state ────────────────────────


@pytest.mark.asyncio
async def test_reverts_after_timeout() -> None:
    """Test is_on reverts to actual cloud state after reconciliation timeout."""
    entity, _ = _make_light(0)

    await entity.async_turn_on()
    assert entity.is_on is True  # optimistic

    # Simulate time passing beyond the timeout
    entity._target_set_at = time.monotonic() - RECONCILIATION_TIMEOUT - 1

    # Cloud still says 0, timeout expired → should revert to actual state
    assert entity.is_on is False
    assert entity._target_state is None


# ── API failure reverts immediately ──────────────────────────────


@pytest.mark.asyncio
async def test_api_failure_reverts_state() -> None:
    """Test _target_state is cleared when the API call fails."""
    entity, coord = _make_light(0)
    coord.api.set_value = AsyncMock(side_effect=Exception("API error"))

    with pytest.raises(Exception, match="API error"):
        await entity.async_turn_on()

    # Should have reverted
    assert entity._target_state is None
    assert entity.is_on is False
    # async_write_ha_state called twice: once optimistic, once reverting
    assert entity.async_write_ha_state.call_count == 2
