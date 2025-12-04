"""Inverse lock platform tests adapted from switch_as_x."""

from __future__ import annotations

from unittest.mock import patch

import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.const import CONF_ENTITY_ID, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_registry import EntityRegistry

from tests.common import Generator, MockConfigEntry, snapshot_platform


@pytest.fixture(autouse=True)
def mock_lock_platform() -> Generator:
    """Limit the platform to lock."""
    with patch(
        "homeassistant.components.inverse.config_flow.PLATFORMS", [Platform.LOCK]
    ) as mock_platform:
        yield mock_platform


@pytest.mark.asyncio
async def test_inverse_lock_services(hass: HomeAssistant) -> None:
    """Verify lock/unlock services are accepted on inverse lock entity."""
    hass.states.async_set("lock.sample", "locked")

    entry = MockConfigEntry(
        domain="inverse", data={CONF_ENTITY_ID: "lock.sample"}, title="ABC"
    )
    entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    inv_id = "lock.abc"
    await hass.services.async_call("lock", "lock", {"entity_id": inv_id}, blocking=True)
    await hass.services.async_call(
        "lock", "unlock", {"entity_id": inv_id}, blocking=True
    )

    state = hass.states.get(inv_id)
    assert state is not None


@pytest.mark.asyncio
async def test_lock_snapshot(
    hass: HomeAssistant, entity_registry: EntityRegistry, snapshot: SnapshotAssertion
) -> None:
    """Snapshot test for lock platform."""
    hass.states.async_set("lock.sample", "locked")

    entry = MockConfigEntry(
        domain="inverse", data={"entity_id": "lock.sample"}, title="Lock"
    )
    entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    await snapshot_platform(hass, entity_registry, snapshot, entry.entry_id)
