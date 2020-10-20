"""Test the Logitech Harmony Hub activity switches."""

import logging

from homeassistant.components.harmony.const import DOMAIN, SIGNAL_UPDATE_ACTIVITY

# from homeassistant.components.switch import DOMAIN as SWITCH_DOMAIN, SERVICE_TURN_OFF
from homeassistant.const import CONF_HOST, CONF_NAME, STATE_OFF, STATE_ON
from homeassistant.helpers.dispatcher import async_dispatcher_send

from tests.async_mock import patch
from tests.common import MockConfigEntry

# TODO centralize
from tests.components.harmony.test_config_flow import _get_mock_harmonyclient

_LOGGER = logging.getLogger(__name__)


async def test_switch_state_transitions(hass):
    """Test state transitions for harmony activity switches. These signals are sent by callbacks registered by the remote."""
    entry = MockConfigEntry(
        domain=DOMAIN, data={CONF_HOST: "192.0.2.0", CONF_NAME: "Guest Room"}
    )

    harmony_client = _get_mock_harmonyclient()

    with patch(
        "aioharmony.harmonyapi.HarmonyClient",
        return_value=harmony_client,
    ), patch("homeassistant.components.harmony.remote.HarmonyRemote.write_config_file"):
        entry.add_to_hass(hass)
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    # mocks start with current activity == Watch TV
    assert hass.states.is_state("switch.guest_room_watch_tv", STATE_ON)
    assert hass.states.is_state("switch.guest_room_play_music", STATE_OFF)

    # Harmony Hub is turned off
    async_dispatcher_send(
        hass,
        f"{SIGNAL_UPDATE_ACTIVITY}-{entry.unique_id}",
        {"current_activity": -1},
    )
    await hass.async_block_till_done()

    assert hass.states.is_state("switch.guest_room_watch_tv", STATE_OFF)
    assert hass.states.is_state("switch.guest_room_play_music", STATE_OFF)
    # Play Music is turned on
    async_dispatcher_send(
        hass,
        f"{SIGNAL_UPDATE_ACTIVITY}-{entry.unique_id}",
        {"current_activity": "Play Music"},
    )
    await hass.async_block_till_done()

    assert hass.states.is_state("switch.guest_room_watch_tv", STATE_OFF)
    assert hass.states.is_state("switch.guest_room_play_music", STATE_ON)

    # Watch TV is turned on
    async_dispatcher_send(
        hass,
        f"{SIGNAL_UPDATE_ACTIVITY}-{entry.unique_id}",
        {"current_activity": "Watch TV"},
    )
    await hass.async_block_till_done()

    assert hass.states.is_state("switch.guest_room_watch_tv", STATE_ON)
    assert hass.states.is_state("switch.guest_room_play_music", STATE_OFF)

    # Unknown activity is turned on
    async_dispatcher_send(
        hass,
        f"{SIGNAL_UPDATE_ACTIVITY}-{entry.unique_id}",
        {"current_activity": "Some Other Activity"},
    )
    await hass.async_block_till_done()

    assert hass.states.is_state("switch.guest_room_watch_tv", STATE_OFF)
    assert hass.states.is_state("switch.guest_room_play_music", STATE_OFF)
