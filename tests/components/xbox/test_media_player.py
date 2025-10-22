"""Test the Xbox media_player platform."""

from collections.abc import Generator
from unittest.mock import patch

import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from tests.common import MockConfigEntry, snapshot_platform
from tests.typing import MagicMock


@pytest.fixture(autouse=True)
def media_player_only() -> Generator[None]:
    """Enable only the media_player platform."""
    with patch(
        "homeassistant.components.xbox.PLATFORMS",
        [Platform.MEDIA_PLAYER],
    ):
        yield


@pytest.fixture(autouse=True)
def mock_token() -> Generator[MagicMock]:
    """Mock token generator."""
    with patch("secrets.token_hex", return_value="mock_token") as token:
        yield token


@pytest.mark.usefixtures("xbox_live_client")
async def test_media_players(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    snapshot: SnapshotAssertion,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test setup of the Xbox media player platform."""

    config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    assert config_entry.state is ConfigEntryState.LOADED

    await snapshot_platform(hass, entity_registry, snapshot, config_entry.entry_id)
