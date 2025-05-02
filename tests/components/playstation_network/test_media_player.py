"""Test the Playstation Network media player platform."""

from collections.abc import AsyncGenerator
from unittest.mock import patch

import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from tests.common import MockConfigEntry, snapshot_platform


@pytest.fixture(autouse=True)
async def media_player_only() -> AsyncGenerator[None]:
    """Enable only the media_player platform."""
    with patch(
        "homeassistant.components.playstation_network.PLATFORMS",
        [Platform.MEDIA_PLAYER],
    ):
        yield


@pytest.mark.usefixtures("mock_psnawpapi", "mock_token")
async def test_platform(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    snapshot: SnapshotAssertion,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test setup of the PlayStation Network media_player platform."""

    config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    assert config_entry.state is ConfigEntryState.LOADED

    await snapshot_platform(hass, entity_registry, snapshot, config_entry.entry_id)
