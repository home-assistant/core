"""Test GeoNet NZ Quakes diagnostics."""

from __future__ import annotations

from unittest.mock import patch

import pytest
from syrupy import SnapshotAssertion

from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry
from tests.components.diagnostics import get_diagnostics_for_config_entry
from tests.typing import ClientSessionGenerator


@pytest.mark.freeze_time("2024-09-05 15:00:00")
async def test_entry_diagnostics(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    snapshot: SnapshotAssertion,
    config_entry: MockConfigEntry,
) -> None:
    """Test config entry diagnostics."""
    with patch("aio_geojson_client.feed.GeoJsonFeed.update") as mock_feed_update:
        mock_feed_update.return_value = "OK", []

        config_entry.add_to_hass(hass)
        await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()

        result = await get_diagnostics_for_config_entry(hass, hass_client, config_entry)
        assert result == snapshot
