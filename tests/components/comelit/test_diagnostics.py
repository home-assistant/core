"""Tests for Comelit Simplehome diagnostics platform."""

from __future__ import annotations

from unittest.mock import patch

from syrupy import SnapshotAssertion
from syrupy.filters import props

from homeassistant.components.comelit.const import DOMAIN
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant

from .const import (
    BRIDGE_DEVICE_QUERY,
    MOCK_USER_BRIDGE_DATA,
    MOCK_USER_VEDO_DATA,
    VEDO_DEVICE_QUERY,
)

from tests.common import MockConfigEntry
from tests.components.diagnostics import get_diagnostics_for_config_entry
from tests.typing import ClientSessionGenerator


async def test_entry_diagnostics_bridge(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    snapshot: SnapshotAssertion,
) -> None:
    """Test Bridge config entry diagnostics."""
    entry = MockConfigEntry(domain=DOMAIN, data=MOCK_USER_BRIDGE_DATA)
    entry.add_to_hass(hass)

    with (
        patch("aiocomelit.api.ComeliteSerialBridgeApi.login"),
        patch(
            "aiocomelit.api.ComeliteSerialBridgeApi.get_all_devices",
            return_value=BRIDGE_DEVICE_QUERY,
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


async def test_entry_diagnostics_vedo(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    snapshot: SnapshotAssertion,
) -> None:
    """Test Vedo System config entry diagnostics."""
    entry = MockConfigEntry(domain=DOMAIN, data=MOCK_USER_VEDO_DATA)
    entry.add_to_hass(hass)

    with (
        patch("aiocomelit.api.ComelitVedoApi.login"),
        patch(
            "aiocomelit.api.ComelitVedoApi.get_all_areas_and_zones",
            return_value=VEDO_DEVICE_QUERY,
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
