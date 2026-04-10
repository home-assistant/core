"""Tests for the Gaposa data update coordinator."""

from __future__ import annotations

from datetime import timedelta
from unittest.mock import MagicMock

from pygaposa import FirebaseAuthException, GaposaAuthException
import pytest

from homeassistant.components.gaposa.const import UPDATE_INTERVAL, UPDATE_INTERVAL_FAST
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import UpdateFailed

from tests.common import MockConfigEntry


def _get_coordinator(
    entry: MockConfigEntry,
) -> "DataUpdateCoordinatorGaposa":
    """Return the coordinator stored on ``entry.runtime_data``."""
    from homeassistant.components.gaposa.coordinator import DataUpdateCoordinatorGaposa

    assert isinstance(entry.runtime_data, DataUpdateCoordinatorGaposa)
    return entry.runtime_data


async def test_coordinator_populates_data(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
) -> None:
    """After setup the coordinator should expose a dict of motors keyed by id."""
    coordinator = _get_coordinator(init_integration)

    # Two mock motors under one device (see conftest).
    assert coordinator.data is not None
    assert len(coordinator.data) == 2
    keys = set(coordinator.data.keys())
    assert keys == {"DEVICE123.motors.motor-1", "DEVICE123.motors.motor-2"}


async def test_coordinator_normal_refresh_interval(
    hass: HomeAssistant, init_integration: MockConfigEntry
) -> None:
    """After a successful first refresh the interval should be UPDATE_INTERVAL."""
    coordinator = _get_coordinator(init_integration)
    assert coordinator.update_interval == timedelta(seconds=UPDATE_INTERVAL)


async def test_update_failure_shortens_interval(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
    mock_gaposa_instance: MagicMock,
) -> None:
    """A failed refresh should flip the coordinator to the fast interval."""
    coordinator = _get_coordinator(init_integration)
    mock_gaposa_instance.update.side_effect = OSError("boom")

    with pytest.raises(UpdateFailed):
        await coordinator._async_update_data()

    assert coordinator.update_interval == timedelta(seconds=UPDATE_INTERVAL_FAST)


async def test_recovery_restores_normal_interval(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
    mock_gaposa_instance: MagicMock,
) -> None:
    """After a recovered refresh the interval returns to UPDATE_INTERVAL."""
    coordinator = _get_coordinator(init_integration)

    mock_gaposa_instance.update.side_effect = OSError("boom")
    with pytest.raises(UpdateFailed):
        await coordinator._async_update_data()
    assert coordinator.update_interval == timedelta(seconds=UPDATE_INTERVAL_FAST)

    mock_gaposa_instance.update.side_effect = None
    await coordinator._async_update_data()
    assert coordinator.update_interval == timedelta(seconds=UPDATE_INTERVAL)


@pytest.mark.parametrize(
    "exc",
    [GaposaAuthException, FirebaseAuthException],
)
async def test_auth_errors_raise_config_entry_auth_failed(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
    mock_gaposa_instance: MagicMock,
    exc: type[Exception],
) -> None:
    """A Gaposa/Firebase auth error on refresh surfaces as ConfigEntryAuthFailed."""
    from homeassistant.exceptions import ConfigEntryAuthFailed

    coordinator = _get_coordinator(init_integration)
    mock_gaposa_instance.update.side_effect = exc("credentials rejected")

    with pytest.raises(ConfigEntryAuthFailed):
        await coordinator._async_update_data()


async def test_on_document_updated_pushes_data(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
) -> None:
    """on_document_updated should synchronously push new data to subscribers."""
    coordinator = _get_coordinator(init_integration)

    initial = coordinator.data.copy()
    coordinator.on_document_updated()
    # Same content shape, but a fresh dict instance (async_set_updated_data
    # notifies listeners and publishes new data).
    assert coordinator.data == initial
