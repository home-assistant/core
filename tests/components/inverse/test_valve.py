"""Inverse valve platform tests adapted from switch_as_x."""

from __future__ import annotations

from unittest.mock import patch

import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.const import CONF_ENTITY_ID, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_registry import EntityRegistry

from tests.common import Generator, MockConfigEntry, snapshot_platform


@pytest.fixture(autouse=True)
def mock_valve_platform() -> Generator:
    """Limit the platform to valve."""
    with patch(
        "homeassistant.components.inverse.config_flow.PLATFORMS", [Platform.VALVE]
    ) as mock_platform:
        yield mock_platform


@pytest.mark.asyncio
async def test_inverse_valve_position_inversion(hass: HomeAssistant) -> None:
    """Verify set_valve_position is accepted and entity exists."""
    hass.states.async_set("valve.sample", "open", {"current_position": 10})

    entry = MockConfigEntry(
        domain="inverse", data={CONF_ENTITY_ID: "valve.sample"}, title="ABC"
    )
    entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    inv_id = "valve.abc"
    await hass.services.async_call(
        "valve",
        "set_valve_position",
        {"entity_id": inv_id, "position": 70},
        blocking=True,
    )

    state = hass.states.get(inv_id)
    assert state is not None


@pytest.mark.asyncio
async def test_valve_snapshot(
    hass: HomeAssistant, entity_registry: EntityRegistry, snapshot: SnapshotAssertion
) -> None:
    """Snapshot test for valve platform."""
    hass.states.async_set("valve.sample", "open", {"current_position": 10})

    entry = MockConfigEntry(
        domain="inverse", data={"entity_id": "valve.sample"}, title="Valve"
    )
    entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    await snapshot_platform(hass, entity_registry, snapshot, entry.entry_id)
