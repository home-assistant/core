"""The test for the Nord Pool sensor platform."""

from __future__ import annotations

import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from tests.common import snapshot_platform


@pytest.mark.freeze_time("2024-11-05T18:00:00+00:00")
@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_sensor(
    hass: HomeAssistant,
    load_int: ConfigEntry,
    entity_registry: er.EntityRegistry,
    snapshot: SnapshotAssertion,
) -> None:
    """Test the Nord Pool sensor."""

    await snapshot_platform(hass, entity_registry, snapshot, load_int.entry_id)
