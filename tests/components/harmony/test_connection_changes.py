"""Test the Logitech Harmony Hub entities with connection state changes."""

from homeassistant.components.harmony.const import DOMAIN
from homeassistant.const import (
    CONF_HOST,
    CONF_NAME,
    STATE_OFF,
    STATE_ON,
    STATE_UNAVAILABLE,
)

from .conftest import FakeHarmonyClient
from .const import ENTITY_PLAY_MUSIC, ENTITY_REMOTE, ENTITY_WATCH_TV, HUB_NAME

from tests.async_mock import AsyncMock, patch
from tests.common import MockConfigEntry


@patch(
    "homeassistant.components.harmony.data.HarmonyClient", side_effect=FakeHarmonyClient
)
@patch(
    "homeassistant.components.harmony.remote.HarmonyRemote.sleep",
    new_callable=AsyncMock,
)
async def test_connection_state_changes(sleep, hc_init, hass):
    """Ensure connection changes are reflected in the switch states."""
    entry = MockConfigEntry(
        domain=DOMAIN, data={CONF_HOST: "192.0.2.0", CONF_NAME: HUB_NAME}
    )

    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    data = hass.data[DOMAIN][entry.entry_id]

    # mocks start with current activity == Watch TV
    assert hass.states.is_state(ENTITY_REMOTE, STATE_ON)
    assert hass.states.is_state(ENTITY_WATCH_TV, STATE_ON)
    assert hass.states.is_state(ENTITY_PLAY_MUSIC, STATE_OFF)

    data._disconnected()
    await hass.async_block_till_done()

    # TODO delay for remote

    assert hass.states.is_state(ENTITY_REMOTE, STATE_UNAVAILABLE)
    assert hass.states.is_state(ENTITY_WATCH_TV, STATE_UNAVAILABLE)
    assert hass.states.is_state(ENTITY_PLAY_MUSIC, STATE_UNAVAILABLE)

    data._connected()
    await hass.async_block_till_done()

    assert hass.states.is_state(ENTITY_REMOTE, STATE_ON)
    assert hass.states.is_state(ENTITY_WATCH_TV, STATE_ON)
    assert hass.states.is_state(ENTITY_PLAY_MUSIC, STATE_OFF)
