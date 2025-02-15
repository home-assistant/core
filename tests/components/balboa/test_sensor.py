"""Tests of the sensors of the balboa integration."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from syrupy import SnapshotAssertion

from homeassistant.const import STATE_UNKNOWN, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from . import init_integration

from tests.common import snapshot_platform

ENTITY_SENSOR = "sensor.fakespa_fault"


async def test_sensors(
    hass: HomeAssistant,
    client: MagicMock,
    entity_registry: er.EntityRegistry,
    snapshot: SnapshotAssertion,
) -> None:
    """Test spa sensors."""
    with patch("homeassistant.components.balboa.PLATFORMS", [Platform.SENSOR]):
        entry = await init_integration(hass)

    await snapshot_platform(hass, entity_registry, snapshot, entry.entry_id)


async def test_sensor(hass: HomeAssistant, client: MagicMock) -> None:
    """Test spa filter cycle enabled sensor."""
    await init_integration(hass)

    # check the state is what we expect
    state = hass.states.get(ENTITY_SENSOR)
    assert state.state == "2025-02-15 13:00: TEST (1/2)"

    # set to unknown
    setattr(client, "fault", None)
    client.emit("")
    await hass.async_block_till_done()

    # check unknown state is what we expect
    state = hass.states.get(ENTITY_SENSOR)
    assert state.state == STATE_UNKNOWN
