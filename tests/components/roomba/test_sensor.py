"""Tests for IRobotEntity usage in Roomba sensor platform."""

from unittest.mock import AsyncMock, patch

import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from tests.common import MockConfigEntry, snapshot_platform


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_entities(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_roomba: AsyncMock,
    snapshot: SnapshotAssertion,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test roomba entities."""
    with patch("homeassistant.components.roomba.PLATFORMS", [Platform.SENSOR]):
        mock_config_entry.add_to_hass(hass)
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)


async def test_rssi_refreshes_on_wifi_only_message(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_roomba: AsyncMock,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test the RSSI sensor refreshes on a message that only carries signal.

    IRobotEntity.new_state_filter drops messages whose only reported key is
    "signal" so a Wi-Fi update does not wake every entity. The RSSI sensor
    reads exactly that key, so it has to opt back in or it never updates.
    """
    entity_id = "sensor.test_roomba_signal_strength"
    with patch("homeassistant.components.roomba.PLATFORMS", [Platform.SENSOR]):
        mock_config_entry.add_to_hass(hass)
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    entity_registry.async_update_entity(entity_id, disabled_by=None)
    await hass.config_entries.async_reload(mock_config_entry.entry_id)
    await hass.async_block_till_done()
    assert hass.states.get(entity_id).state == "-47"

    # A Wi-Fi only update, which is what the robot sends most often.
    mock_roomba.master_state["state"]["reported"]["signal"]["rssi"] = -62
    for call in mock_roomba.register_on_message_callback.call_args_list:
        call.args[0]({"state": {"reported": {"signal": {"rssi": -62}}}})
    await hass.async_block_till_done()

    assert hass.states.get(entity_id).state == "-62"
