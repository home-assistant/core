"""Tests for Vodafone Station diagnostics platform."""

from __future__ import annotations

from unittest.mock import patch

from syrupy import SnapshotAssertion
from syrupy.filters import props

from homeassistant.components.vodafone_station.const import DOMAIN
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant

from .const import DEVICE_DATA_QUERY, MOCK_USER_DATA, SENSOR_DATA_QUERY

from tests.common import MockConfigEntry
from tests.components.diagnostics import get_diagnostics_for_config_entry
from tests.typing import ClientSessionGenerator


async def test_entry_diagnostics(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    snapshot: SnapshotAssertion,
) -> None:
    """Test config entry diagnostics."""
    entry = MockConfigEntry(domain=DOMAIN, data=MOCK_USER_DATA)
    entry.add_to_hass(hass)

    with (
        patch("aiovodafone.api.VodafoneStationSercommApi.login"),
        patch(
            "aiovodafone.api.VodafoneStationSercommApi.get_devices_data",
            return_value=DEVICE_DATA_QUERY,
        ),
        patch(
            "aiovodafone.api.VodafoneStationSercommApi.get_sensor_data",
            return_value=SENSOR_DATA_QUERY,
        ),
    ):
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    assert entry.state == ConfigEntryState.LOADED
    assert await get_diagnostics_for_config_entry(hass, hass_client, entry) == snapshot(
        exclude=props(
            "entry_id",
            "created_at",
            "modified_at",
        )
    )
