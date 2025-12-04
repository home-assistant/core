"""Inverse light platform tests adapted from switch_as_x."""

from __future__ import annotations

from unittest.mock import patch

import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.const import CONF_ENTITY_ID, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_registry import EntityRegistry

from tests.common import Generator, MockConfigEntry, snapshot_platform


@pytest.fixture(autouse=True)
def mock_light_platform() -> Generator:
    """Limit the platform to light."""
    with patch(
        "homeassistant.components.inverse.config_flow.PLATFORMS", [Platform.LIGHT]
    ) as mock_platform:
        yield mock_platform


@pytest.mark.asyncio
async def test_inverse_light_toggle(hass: HomeAssistant) -> None:
    """Verify turn_on/turn_off are accepted on inverse light entity."""
    hass.states.async_set("light.sample", "on")

    entry = MockConfigEntry(
        domain="inverse", data={CONF_ENTITY_ID: "light.sample"}, title="ABC"
    )
    entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    inv_id = "light.abc"
    await hass.services.async_call(
        "light", "turn_on", {"entity_id": inv_id}, blocking=True
    )
    await hass.services.async_call(
        "light", "turn_off", {"entity_id": inv_id}, blocking=True
    )

    assert hass.states.get(inv_id) is not None


@pytest.mark.asyncio
async def test_light_snapshot(
    hass: HomeAssistant, entity_registry: EntityRegistry, snapshot: SnapshotAssertion
) -> None:
    """Snapshot test for light platform."""
    hass.states.async_set("light.sample", "on")

    entry = MockConfigEntry(
        domain="inverse", data={"entity_id": "light.sample"}, title="Light"
    )
    entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    await snapshot_platform(hass, entity_registry, snapshot, entry.entry_id)
