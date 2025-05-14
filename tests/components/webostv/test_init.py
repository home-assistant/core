"""The tests for the LG webOS TV platform."""

from aiowebostv import WebOsTvPairError

from homeassistant.components.media_player import ATTR_INPUT_SOURCE_LIST
from homeassistant.components.webostv.const import CONF_SOURCES, DOMAIN
from homeassistant.config_entries import SOURCE_REAUTH, ConfigEntryState
from homeassistant.const import CONF_CLIENT_SECRET, EVENT_HOMEASSISTANT_STOP
from homeassistant.core import HomeAssistant

from . import setup_webostv
from .const import ENTITY_ID


async def test_reauth_setup_entry(hass: HomeAssistant, client) -> None:
    """Test reauth flow triggered by setup entry."""
    client.is_connected.return_value = False
    client.connect.side_effect = WebOsTvPairError
    entry = await setup_webostv(hass)

    assert entry.state is ConfigEntryState.SETUP_ERROR

    flows = hass.config_entries.flow.async_progress()
    assert len(flows) == 1

    flow = flows[0]
    assert flow.get("step_id") == "reauth_confirm"
    assert flow.get("handler") == DOMAIN

    assert "context" in flow
    assert flow["context"].get("source") == SOURCE_REAUTH
    assert flow["context"].get("entry_id") == entry.entry_id


async def test_key_update_setup_entry(hass: HomeAssistant, client) -> None:
    """Test key update from setup entry."""
    client.client_key = "new_key"
    entry = await setup_webostv(hass)

    assert entry.state is ConfigEntryState.LOADED
    assert entry.data[CONF_CLIENT_SECRET] == "new_key"


async def test_update_options(hass: HomeAssistant, client) -> None:
    """Test update options triggers reload."""
    config_entry = await setup_webostv(hass)

    assert config_entry.state is ConfigEntryState.LOADED
    assert config_entry.update_listeners is not None
    sources = hass.states.get(ENTITY_ID).attributes[ATTR_INPUT_SOURCE_LIST]
    assert sources == ["Input01", "Input02", "Live TV"]

    # remove Input01 and reload
    new_options = config_entry.options.copy()
    new_options[CONF_SOURCES] = ["Input02", "Live TV"]
    hass.config_entries.async_update_entry(config_entry, options=new_options)
    await hass.async_block_till_done()

    assert config_entry.state is ConfigEntryState.LOADED
    sources = hass.states.get(ENTITY_ID).attributes[ATTR_INPUT_SOURCE_LIST]
    assert sources == ["Input02", "Live TV"]


async def test_disconnect_on_stop(hass: HomeAssistant, client) -> None:
    """Test we disconnect the client and clear callbacks when Home Assistants stops."""
    config_entry = await setup_webostv(hass)

    assert client.disconnect.call_count == 0
    assert client.clear_state_update_callbacks.call_count == 0
    assert config_entry.state is ConfigEntryState.LOADED

    hass.bus.async_fire(EVENT_HOMEASSISTANT_STOP)
    await hass.async_block_till_done()

    assert client.disconnect.call_count == 1
    assert client.clear_state_update_callbacks.call_count == 1
    assert config_entry.state is ConfigEntryState.LOADED
