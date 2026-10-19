"""Tests for the System Bridge update platform."""

from collections.abc import Generator
from dataclasses import replace
from unittest.mock import MagicMock, patch

import pytest
from syrupy.assertion import SnapshotAssertion
from systembridgeconnector.models.fixtures.modules.system import FIXTURE_SYSTEM
from systembridgeconnector.models.modules import ModulesData

from homeassistant.components.update import ATTR_LATEST_VERSION, ATTR_RELEASE_URL
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from tests.common import MockConfigEntry, snapshot_platform


@pytest.fixture(autouse=True)
def update_only() -> Generator[None]:
    """Enable only the update platform."""
    with patch(
        "homeassistant.components.system_bridge.PLATFORMS",
        [Platform.UPDATE],
    ):
        yield


@pytest.mark.usefixtures(
    "mock_version", "mock_websocket_client", "entity_registry_enabled_by_default"
)
async def test_update_platform(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    snapshot: SnapshotAssertion,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test setup of the update platform."""
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.LOADED

    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)


@pytest.mark.usefixtures("mock_version")
async def test_update_no_latest_version(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_websocket_client: MagicMock,
) -> None:
    """Test the release URL is unknown when there is no latest version."""
    mock_websocket_client.get_data.return_value = ModulesData(
        system=replace(FIXTURE_SYSTEM, version_latest=None)
    )
    mock_websocket_client.listen.side_effect = None

    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.LOADED

    state = hass.states.get("update.hostname")
    assert state
    assert state.attributes[ATTR_LATEST_VERSION] is None
    assert state.attributes[ATTR_RELEASE_URL] is None
