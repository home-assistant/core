"""The tests for the imazu_wall_pad component."""
from unittest.mock import patch

import pytest

from homeassistant.components.imazu_wall_pad.const import PACKET
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant
from homeassistant.helpers.restore_state import RestoredExtraData, RestoreStateData

from . import async_setup
from .const import LIGHT_STATE_OFF_PACKET, LIGHT_TEST_ENTITY_ID


@pytest.mark.usefixtures("mock_imazu_client")
async def test_setup_entry(hass: HomeAssistant):
    """Test setup entry."""
    entry = await async_setup(hass)
    assert entry.state == ConfigEntryState.LOADED


@pytest.mark.usefixtures("mock_imazu_client")
async def test_unload_entry(hass: HomeAssistant):
    """Test unload entry."""
    entry = await async_setup(hass)

    await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()
    assert entry.state is ConfigEntryState.NOT_LOADED


async def test_not_connected_entry(hass: HomeAssistant):
    """Test for setup error the not connected."""
    entry = await async_setup(hass)
    assert entry.state == ConfigEntryState.SETUP_ERROR


async def test_reload_entry(hass: HomeAssistant, mock_imazu_client):
    """Test reload entry."""
    entry = await async_setup(hass)
    assert entry.state == ConfigEntryState.LOADED

    test_packet = bytes.fromhex(LIGHT_STATE_OFF_PACKET)
    await mock_imazu_client.async_receive_packet(test_packet)
    await hass.async_block_till_done()

    await hass.config_entries.async_reload(entry.entry_id)
    await hass.async_block_till_done()
    assert entry.state is ConfigEntryState.LOADED

    entity_registry = hass.helpers.entity_registry.async_get(hass)
    entities = hass.helpers.entity_registry.async_entries_for_config_entry(
        entity_registry, entry.entry_id
    )
    assert len(entities) == 1


async def test_restore_empty_last_states(hass: HomeAssistant, mock_imazu_client):
    """Test for restore the empty last states."""
    entry = await async_setup(hass)
    test_packet = bytes.fromhex(LIGHT_STATE_OFF_PACKET)
    await mock_imazu_client.async_receive_packet(test_packet)
    await hass.async_block_till_done()

    with patch(
        "homeassistant.helpers.restore_state.RestoreEntity.async_internal_will_remove_from_hass",
        return_value=None,
    ):
        await hass.config_entries.async_reload(entry.entry_id)
        await hass.async_block_till_done()

    data = await RestoreStateData.async_get_instance(hass)
    assert len(data.last_states) == 0

    state = hass.states.get(LIGHT_TEST_ENTITY_ID)
    assert state and state.state == "unavailable"


async def test_restore_none_extra_data(hass: HomeAssistant, mock_imazu_client):
    """Test for restore the none extra data."""
    entry = await async_setup(hass)
    test_packet = bytes.fromhex(LIGHT_STATE_OFF_PACKET)
    await mock_imazu_client.async_receive_packet(test_packet)
    await hass.async_block_till_done()

    with patch(
        "homeassistant.components.imazu_wall_pad.wall_pad.WallPadDevice.extra_restore_state_data",
        None,
    ):
        await hass.config_entries.async_reload(entry.entry_id)
        await hass.async_block_till_done()

    data = await RestoreStateData.async_get_instance(hass)
    last_state = data.last_states[LIGHT_TEST_ENTITY_ID]
    assert last_state and last_state.extra_data is None

    state = hass.states.get(LIGHT_TEST_ENTITY_ID)
    assert state and state.state == "unavailable"


async def test_restore_none_packet(hass: HomeAssistant, mock_imazu_client):
    """Test for restore the none packet."""
    entry = await async_setup(hass)
    test_packet = bytes.fromhex(LIGHT_STATE_OFF_PACKET)
    await mock_imazu_client.async_receive_packet(test_packet)
    await hass.async_block_till_done()

    with patch(
        "homeassistant.components.imazu_wall_pad.wall_pad.WallPadDevice.extra_restore_state_data",
        RestoredExtraData({}),
    ):
        await hass.config_entries.async_reload(entry.entry_id)
        await hass.async_block_till_done()

    data = await RestoreStateData.async_get_instance(hass)
    last_state = data.last_states[LIGHT_TEST_ENTITY_ID]
    assert last_state.extra_data and PACKET not in last_state.extra_data.as_dict()

    state = hass.states.get(LIGHT_TEST_ENTITY_ID)
    assert state and state.state == "unavailable"
