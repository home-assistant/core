"""Test the Logitech Harmony Hub activity switches."""

import logging

from homeassistant.components.harmony.const import DOMAIN

# from homeassistant.components.switch import DOMAIN as SWITCH_DOMAIN, SERVICE_TURN_OFF
from homeassistant.const import CONF_HOST, CONF_NAME, STATE_OFF, STATE_ON

from tests.async_mock import patch
from tests.common import MockConfigEntry

# TODO centralize
from tests.components.harmony.test_config_flow import _get_mock_harmonyclient

# from homeassistant.helpers.dispatcher import async_dispatcher_send


_LOGGER = logging.getLogger(__name__)


async def test_switch_state_transitions(hass):
    """Test state transitions for harmony activity switches."""
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

    # _LOGGER.info("WAFFLES %s", hass.services.async_call)
    # call = hass.services.async_call(
    # SWITCH_DOMAIN,
    # SERVICE_TURN_OFF,
    # { ATTR_ENTITY_ID: "switch.guest_room_watch_tv"},
    # blocking=True,
    # )
    # _LOGGER.info("WAFFLES %s", call)
    # await call

    # assert hass.states.is_state("switch.guest_room_watch_tv", STATE_OFF)
    # assert hass.states.is_state("switch.guest_room_play_music", STATE_OFF)
