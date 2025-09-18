"""Tests for the VRM Forecasts sensors.

Consolidates most per-sensor assertions into snapshot-based regression tests.
"""

from __future__ import annotations

import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from tests.common import snapshot_platform


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_sensors_snapshot(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    init_integration,
    snapshot: SnapshotAssertion,
) -> None:
    """Snapshot all VRM sensor states & key attributes."""
    await snapshot_platform(hass, entity_registry, snapshot, init_integration.entry_id)
