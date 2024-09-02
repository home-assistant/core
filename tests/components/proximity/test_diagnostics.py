"""Tests for proximity diagnostics platform."""

from __future__ import annotations

from syrupy.assertion import SnapshotAssertion
from syrupy.filters import props

from homeassistant.components.proximity.const import (
    CONF_IGNORED_ZONES,
    CONF_TOLERANCE,
    CONF_TRACKED_ENTITIES,
    DOMAIN,
)
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import CONF_ZONE
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry
from tests.components.diagnostics import get_diagnostics_for_config_entry
from tests.typing import ClientSessionGenerator


async def test_entry_diagnostics(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    snapshot: SnapshotAssertion,
) -> None:
    """Test config entry diagnostics."""
    hass.states.async_set(
        "device_tracker.test1",
        "not_home",
        {"friendly_name": "test1", "latitude": 20.1, "longitude": 10.1},
    )
    hass.states.async_set(
        "device_tracker.test2",
        "not_home",
        {"friendly_name": "test2", "latitude": 150.1, "longitude": 20.1},
    )
    hass.states.async_set(
        "device_tracker.test3",
        "my secret address",
        {
            "friendly_name": "test3",
            "latitude": 150.1,
            "longitude": 20.1,
            "location_name": "my secret address",
        },
    )

    mock_entry = MockConfigEntry(
        domain=DOMAIN,
        title="home",
        data={
            CONF_ZONE: "zone.home",
            CONF_TRACKED_ENTITIES: [
                "device_tracker.test1",
                "device_tracker.test2",
                "device_tracker.test3",
                "device_tracker.test4",
            ],
            CONF_IGNORED_ZONES: [],
            CONF_TOLERANCE: 1,
        },
        unique_id=f"{DOMAIN}_home",
    )

    mock_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(mock_entry.entry_id)
    await hass.async_block_till_done()
    assert mock_entry.state is ConfigEntryState.LOADED

    assert await get_diagnostics_for_config_entry(
        hass, hass_client, mock_entry
    ) == snapshot(
        exclude=props(
            "entry_id",
            "last_changed",
            "last_reported",
            "last_updated",
            "created_at",
            "modified_at",
        )
    )
