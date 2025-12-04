"""Inverse switch platform tests adapted from switch_as_x."""

from __future__ import annotations

from unittest.mock import patch

import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.const import CONF_ENTITY_ID, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_registry import EntityRegistry

from tests.common import Generator, MockConfigEntry, snapshot_platform


@pytest.fixture(autouse=True)
def mock_switch_platform() -> Generator:
    """Limit the platform to switch."""
    with patch(
        "homeassistant.components.inverse.config_flow.PLATFORMS", [Platform.SWITCH]
    ) as mock_platform:
        yield mock_platform


@pytest.mark.asyncio
async def test_inverse_switch_toggle(hass: HomeAssistant) -> None:
    """Verify turn_on/turn_off are accepted on inverse switch entity."""
    hass.states.async_set("switch.sample", "off")

    entry = MockConfigEntry(
        domain="inverse", data={CONF_ENTITY_ID: "switch.sample"}, title="ABC"
    )
    entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    inv_id = "switch.abc"
    await hass.services.async_call(
        "switch", "turn_on", {"entity_id": inv_id}, blocking=True
    )
    await hass.services.async_call(
        "switch", "turn_off", {"entity_id": inv_id}, blocking=True
    )

    assert hass.states.get(inv_id) is not None


@pytest.mark.asyncio
async def test_switch_snapshot(
    hass: HomeAssistant, entity_registry: EntityRegistry, snapshot: SnapshotAssertion
) -> None:
    """Snapshot test for switch platform."""
    hass.states.async_set("switch.sample", "off")

    entry = MockConfigEntry(
        domain="inverse", data={"entity_id": "switch.sample"}, title="Switch"
    )
    entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    await snapshot_platform(hass, entity_registry, snapshot, entry.entry_id)
