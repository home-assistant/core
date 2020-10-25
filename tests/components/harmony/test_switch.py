"""Test the Logitech Harmony Hub activity switches."""

import logging

from homeassistant.components.harmony.const import (
    CONNECTION_UPDATE_ACTIVITY,
    DOMAIN,
    SIGNAL_UPDATE_ACTIVITY,
)
from homeassistant.components.switch import (
    DOMAIN as SWITCH_DOMAIN,
    SERVICE_TURN_OFF,
    SERVICE_TURN_ON,
)
from homeassistant.const import (
    ATTR_ENTITY_ID,
    CONF_HOST,
    CONF_NAME,
    STATE_OFF,
    STATE_ON,
    STATE_UNAVAILABLE,
)
from homeassistant.helpers.dispatcher import async_dispatcher_send

from tests.async_mock import patch
from tests.common import MockConfigEntry
from tests.components.harmony.conftest import (
    PLAY_MUSIC_ACTIVITY_ID,
    WATCH_TV_ACTIVITY_ID,
)

_LOGGER = logging.getLogger(__name__)

ENTITY_WATCH_TV = "switch.guest_room_watch_tv"
ENTITY_PLAY_MUSIC = "switch.guest_room_play_music"


async def test_state_transitions(hass, mock_harmonyclient):
    """Test state transitions for harmony activity switches. These signals are sent by callbacks registered by the remote."""
    entry = MockConfigEntry(
        domain=DOMAIN, data={CONF_HOST: "192.0.2.0", CONF_NAME: "Guest Room"}
    )

    with patch(
        "aioharmony.harmonyapi.HarmonyClient",
        return_value=mock_harmonyclient,
    ), patch("homeassistant.components.harmony.remote.HarmonyRemote.write_config_file"):
        entry.add_to_hass(hass)
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    # mocks start with current activity == Watch TV
    assert hass.states.is_state(ENTITY_WATCH_TV, STATE_ON)
    assert hass.states.is_state(ENTITY_PLAY_MUSIC, STATE_OFF)

    # Harmony Hub is turned off
    async_dispatcher_send(
        hass,
        f"{SIGNAL_UPDATE_ACTIVITY}-{entry.unique_id}",
        {"current_activity": -1},
    )
    await hass.async_block_till_done()

    assert hass.states.is_state(ENTITY_WATCH_TV, STATE_OFF)
    assert hass.states.is_state(ENTITY_PLAY_MUSIC, STATE_OFF)
    # Play Music is turned on
    async_dispatcher_send(
        hass,
        f"{SIGNAL_UPDATE_ACTIVITY}-{entry.unique_id}",
        {"current_activity": "Play Music"},
    )
    await hass.async_block_till_done()

    assert hass.states.is_state(ENTITY_WATCH_TV, STATE_OFF)
    assert hass.states.is_state(ENTITY_PLAY_MUSIC, STATE_ON)

    # Watch TV is turned on
    async_dispatcher_send(
        hass,
        f"{SIGNAL_UPDATE_ACTIVITY}-{entry.unique_id}",
        {"current_activity": "Watch TV"},
    )
    await hass.async_block_till_done()

    assert hass.states.is_state(ENTITY_WATCH_TV, STATE_ON)
    assert hass.states.is_state(ENTITY_PLAY_MUSIC, STATE_OFF)

    # Unknown activity is turned on
    async_dispatcher_send(
        hass,
        f"{SIGNAL_UPDATE_ACTIVITY}-{entry.unique_id}",
        {"current_activity": "Some Other Activity"},
    )
    await hass.async_block_till_done()

    assert hass.states.is_state(ENTITY_WATCH_TV, STATE_OFF)
    assert hass.states.is_state(ENTITY_PLAY_MUSIC, STATE_OFF)


async def test_availability_transitions(hass, mock_harmonyclient):
    """Test transitions for harmony hub availability."""
    entry = MockConfigEntry(
        domain=DOMAIN, data={CONF_HOST: "192.0.2.0", CONF_NAME: "Guest Room"}
    )

    with patch(
        "aioharmony.harmonyapi.HarmonyClient",
        return_value=mock_harmonyclient,
    ), patch("homeassistant.components.harmony.remote.HarmonyRemote.write_config_file"):
        entry.add_to_hass(hass)
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    # mocks start with current activity == Watch TV
    assert hass.states.is_state(ENTITY_WATCH_TV, STATE_ON)
    assert hass.states.is_state(ENTITY_PLAY_MUSIC, STATE_OFF)

    async_dispatcher_send(
        hass,
        f"{CONNECTION_UPDATE_ACTIVITY}-{entry.unique_id}",
        {"available": False},
    )
    await hass.async_block_till_done()

    assert hass.states.is_state(ENTITY_WATCH_TV, STATE_UNAVAILABLE)
    assert hass.states.is_state(ENTITY_PLAY_MUSIC, STATE_UNAVAILABLE)

    async_dispatcher_send(
        hass,
        f"{CONNECTION_UPDATE_ACTIVITY}-{entry.unique_id}",
        {"available": True},
    )
    await hass.async_block_till_done()

    assert hass.states.is_state(ENTITY_WATCH_TV, STATE_ON)
    assert hass.states.is_state(ENTITY_PLAY_MUSIC, STATE_OFF)


async def test_switch_toggles(hass, mock_harmonyclient):
    """Ensure calls to the switch call into the harmony client.

    Note the harmonyclient mock is not currently set up to actually change states.
    """
    entry = MockConfigEntry(
        domain=DOMAIN, data={CONF_HOST: "192.0.2.0", CONF_NAME: "Guest Room"}
    )

    with patch(
        "aioharmony.harmonyapi.HarmonyClient",
        return_value=mock_harmonyclient,
    ), patch("homeassistant.components.harmony.remote.HarmonyRemote.write_config_file"):
        entry.add_to_hass(hass)
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    await hass.services.async_call(
        SWITCH_DOMAIN,
        SERVICE_TURN_OFF,
        {ATTR_ENTITY_ID: ENTITY_WATCH_TV},
        blocking=True,
    )

    mock_harmonyclient.start_activity.assert_awaited_with(activity_id=-1)
    await hass.services.async_call(
        SWITCH_DOMAIN,
        SERVICE_TURN_ON,
        {ATTR_ENTITY_ID: ENTITY_PLAY_MUSIC},
        blocking=True,
    )

    mock_harmonyclient.start_activity.assert_awaited_with(
        activity_id=PLAY_MUSIC_ACTIVITY_ID
    )

    # TODO test turning on and off watch tv
    await hass.services.async_call(
        SWITCH_DOMAIN,
        SERVICE_TURN_ON,
        {ATTR_ENTITY_ID: ENTITY_WATCH_TV},
        blocking=True,
    )

    mock_harmonyclient.start_activity.assert_awaited_with(
        activity_id=WATCH_TV_ACTIVITY_ID
    )
