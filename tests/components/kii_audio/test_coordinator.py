"""Tests for the Kii Audio coordinator."""

import asyncio

from aiokii import KiiAudioError

from homeassistant.components.kii_audio.coordinator import KiiAudioCoordinator


def _coordinator() -> KiiAudioCoordinator:
    """Return a minimal coordinator instance for callback tests."""
    coordinator = KiiAudioCoordinator.__new__(KiiAudioCoordinator)
    coordinator._ready = asyncio.Event()
    return coordinator


def test_connection_loss_before_ready_does_not_mark_unavailable() -> None:
    """Test early connection loss is handled by setup timeout instead."""
    coordinator = _coordinator()
    errors: list[Exception] = []
    coordinator.async_set_update_error = errors.append  # type: ignore[method-assign]

    coordinator._handle_connection_state(False)

    assert errors == []


def test_connection_loss_after_ready_marks_coordinator_unavailable() -> None:
    """Test connection loss after setup marks coordinator unavailable."""
    coordinator = _coordinator()
    errors: list[Exception] = []
    coordinator.async_set_update_error = errors.append  # type: ignore[method-assign]
    coordinator._ready.set()

    coordinator._handle_connection_state(False)

    assert len(errors) == 1
    assert isinstance(errors[0], KiiAudioError)
    assert str(errors[0]) == "WebSocket disconnected"


def test_connection_available_does_not_mark_update_error() -> None:
    """Test connected callbacks do not mark update errors."""
    coordinator = _coordinator()
    errors: list[Exception] = []
    coordinator.async_set_update_error = errors.append  # type: ignore[method-assign]
    coordinator._ready.set()

    coordinator._handle_connection_state(True)

    assert errors == []
