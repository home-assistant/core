"""Tests for IronOS update platform."""

from collections.abc import AsyncGenerator
from unittest.mock import AsyncMock, patch

from pynecil import CommunicationError, UpdateException
import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.update import ATTR_INSTALLED_VERSION
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import STATE_ON, STATE_UNAVAILABLE, Platform
from homeassistant.core import HomeAssistant, State
from homeassistant.helpers import entity_registry as er

from tests.common import MockConfigEntry, mock_restore_cache, snapshot_platform
from tests.typing import WebSocketGenerator


@pytest.fixture(autouse=True)
async def update_only() -> AsyncGenerator[None]:
    """Enable only the update platform."""
    with patch(
        "homeassistant.components.iron_os.PLATFORMS",
        [Platform.UPDATE],
    ):
        yield


@pytest.mark.usefixtures("mock_pynecil", "ble_device", "mock_ironosupdate")
async def test_update(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    snapshot: SnapshotAssertion,
    entity_registry: er.EntityRegistry,
    hass_ws_client: WebSocketGenerator,
) -> None:
    """Test the IronOS update platform."""
    ws_client = await hass_ws_client(hass)

    config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    assert config_entry.state is ConfigEntryState.LOADED

    await snapshot_platform(hass, entity_registry, snapshot, config_entry.entry_id)

    await ws_client.send_json(
        {
            "id": 1,
            "type": "update/release_notes",
            "entity_id": "update.pinecil_firmware",
        }
    )
    result = await ws_client.receive_json()
    assert result["result"] == snapshot


@pytest.mark.usefixtures("ble_device", "mock_pynecil")
async def test_update_unavailable(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    mock_ironosupdate: AsyncMock,
) -> None:
    """Test update entity unavailable on error."""

    mock_ironosupdate.latest_release.side_effect = UpdateException

    config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    assert config_entry.state is ConfigEntryState.LOADED

    state = hass.states.get("update.pinecil_firmware")
    assert state is not None
    assert state.state == STATE_UNAVAILABLE


@pytest.mark.usefixtures("ble_device")
async def test_update_restore_last_state(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    mock_pynecil: AsyncMock,
) -> None:
    """Test update entity restore last state."""

    mock_pynecil.get_device_info.side_effect = CommunicationError
    mock_restore_cache(
        hass,
        (
            State(
                "update.pinecil_firmware",
                STATE_ON,
                attributes={ATTR_INSTALLED_VERSION: "v2.21"},
            ),
        ),
    )
    config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    assert config_entry.state is ConfigEntryState.LOADED

    state = hass.states.get("update.pinecil_firmware")
    assert state is not None
    assert state.state == STATE_ON
    assert state.attributes[ATTR_INSTALLED_VERSION] == "v2.21"
