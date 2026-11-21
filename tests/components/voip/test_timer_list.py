"""Test VoIP timer lists."""

from datetime import timedelta
from unittest.mock import patch

from pytest_homeassistant.common import MockConfigEntry

from homeassistant.components.timer_list import async_get_timer_list_entity
from homeassistant.components.voip.assist_satellite import VoipAssistSatellite
from homeassistant.components.voip.devices import VoIPDevice
from homeassistant.core import HomeAssistant

TIMER_LIST_ENTITY_ID = "timer_list.192_168_1_210_timers"


async def test_timer_list(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    voip_device: VoIPDevice,
) -> None:
    """Test a VoIP device gets a timer list, also when loaded from the registry."""
    state = hass.states.get(TIMER_LIST_ENTITY_ID)
    assert state is not None
    assert state.state == "0"

    await hass.config_entries.async_reload(config_entry.entry_id)
    await hass.async_block_till_done()

    state = hass.states.get(TIMER_LIST_ENTITY_ID)
    assert state is not None
    assert state.state == "0"


async def test_timer_list_entity_id(
    hass: HomeAssistant, satellite: VoipAssistSatellite
) -> None:
    """Test the satellite reports the timer list of its device."""
    assert satellite.timer_list_entity_id == TIMER_LIST_ENTITY_ID


async def test_timer_finished_without_satellite(
    hass: HomeAssistant, voip_device: VoIPDevice
) -> None:
    """Test a timer finishing while the device has no satellite announces nothing."""
    timer_list = async_get_timer_list_entity(hass, TIMER_LIST_ENTITY_ID)
    assert timer_list is not None
    assert timer_list.entity_id == TIMER_LIST_ENTITY_ID
    timer_id = await timer_list.async_create_timer(
        name=None, duration=timedelta(minutes=2)
    )

    with (
        patch.object(voip_device, "protocol", None),
        patch.object(VoipAssistSatellite, "async_announce_timer") as mock_handle,
    ):
        await timer_list.async_finish_timer(timer_id)
        await hass.async_block_till_done()

    mock_handle.assert_not_called()
