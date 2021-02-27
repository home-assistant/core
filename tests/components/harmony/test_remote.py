"""Test the Logitech Harmony Hub remote."""

from datetime import timedelta

from homeassistant.components.harmony.const import DOMAIN
from homeassistant.components.remote import (
    ATTR_ACTIVITY,
    DOMAIN as REMOTE_DOMAIN,
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
from homeassistant.util import utcnow

from .conftest import ACTIVITIES_TO_IDS
from .const import ENTITY_PLAY_MUSIC, ENTITY_REMOTE, ENTITY_WATCH_TV, HUB_NAME

from tests.common import MockConfigEntry, async_fire_time_changed


async def test_connection_state_changes(
    harmony_client, mock_hc, hass, mock_write_config
):
    """Ensure connection changes are reflected in the remote state."""
    entry = MockConfigEntry(
        domain=DOMAIN, data={CONF_HOST: "192.0.2.0", CONF_NAME: HUB_NAME}
    )

    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    # mocks start with current activity == Watch TV
    assert hass.states.is_state(ENTITY_REMOTE, STATE_ON)

    harmony_client.mock_disconnection()
    await hass.async_block_till_done()

    # Entities do not immediately show as unavailable
    assert hass.states.is_state(ENTITY_REMOTE, STATE_ON)

    future_time = utcnow() + timedelta(seconds=10)
    async_fire_time_changed(hass, future_time)
    await hass.async_block_till_done()
    assert hass.states.is_state(ENTITY_REMOTE, STATE_UNAVAILABLE)

    harmony_client.mock_reconnection()
    await hass.async_block_till_done()

    assert hass.states.is_state(ENTITY_REMOTE, STATE_ON)

    harmony_client.mock_disconnection()
    harmony_client.mock_reconnection()
    future_time = utcnow() + timedelta(seconds=10)
    async_fire_time_changed(hass, future_time)

    await hass.async_block_till_done()
    assert hass.states.is_state(ENTITY_REMOTE, STATE_ON)


async def test_remote_toggles(mock_hc, hass, mock_write_config):
    """Ensure calls to the remote also updates the switches."""
    entry = MockConfigEntry(
        domain=DOMAIN, data={CONF_HOST: "192.0.2.0", CONF_NAME: HUB_NAME}
    )

    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    # mocks start with current activity == Watch TV
    assert hass.states.is_state(ENTITY_REMOTE, STATE_ON)
    assert hass.states.is_state(ENTITY_WATCH_TV, STATE_ON)
    assert hass.states.is_state(ENTITY_PLAY_MUSIC, STATE_OFF)

    # turn off remote
    await hass.services.async_call(
        REMOTE_DOMAIN,
        SERVICE_TURN_OFF,
        {ATTR_ENTITY_ID: ENTITY_REMOTE},
        blocking=True,
    )
    await hass.async_block_till_done()

    assert hass.states.is_state(ENTITY_REMOTE, STATE_OFF)
    assert hass.states.is_state(ENTITY_WATCH_TV, STATE_OFF)
    assert hass.states.is_state(ENTITY_PLAY_MUSIC, STATE_OFF)

    # turn on remote, restoring the last activity
    await hass.services.async_call(
        REMOTE_DOMAIN,
        SERVICE_TURN_ON,
        {ATTR_ENTITY_ID: ENTITY_REMOTE},
        blocking=True,
    )
    await hass.async_block_till_done()

    assert hass.states.is_state(ENTITY_REMOTE, STATE_ON)
    assert hass.states.is_state(ENTITY_WATCH_TV, STATE_ON)
    assert hass.states.is_state(ENTITY_PLAY_MUSIC, STATE_OFF)

    # send new activity command, with activity name
    await hass.services.async_call(
        REMOTE_DOMAIN,
        SERVICE_TURN_ON,
        {ATTR_ENTITY_ID: ENTITY_REMOTE, ATTR_ACTIVITY: "Play Music"},
        blocking=True,
    )
    await hass.async_block_till_done()

    assert hass.states.is_state(ENTITY_REMOTE, STATE_ON)
    assert hass.states.is_state(ENTITY_WATCH_TV, STATE_OFF)
    assert hass.states.is_state(ENTITY_PLAY_MUSIC, STATE_ON)

    # send new activity command, with activity id
    await hass.services.async_call(
        REMOTE_DOMAIN,
        SERVICE_TURN_ON,
        {ATTR_ENTITY_ID: ENTITY_REMOTE, ATTR_ACTIVITY: ACTIVITIES_TO_IDS["Watch TV"]},
        blocking=True,
    )
    await hass.async_block_till_done()

    assert hass.states.is_state(ENTITY_REMOTE, STATE_ON)
    assert hass.states.is_state(ENTITY_WATCH_TV, STATE_ON)
    assert hass.states.is_state(ENTITY_PLAY_MUSIC, STATE_OFF)
