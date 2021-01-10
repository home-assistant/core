"""Test the Z-Wave JS init module."""
from homeassistant.config_entries import ENTRY_STATE_LOADED, ENTRY_STATE_NOT_LOADED
from homeassistant.const import STATE_UNAVAILABLE

AIR_TEMPERATURE_SENSOR = "sensor.multisensor_6_air_temperature"


async def test_entry_setup_unload(hass, client, integration):
    """Test the integration set up and unload."""
    entry = integration

    assert client.connect.call_count == 1
    assert client.register_on_initialized.call_count == 1
    assert client.register_on_disconnect.call_count == 1
    assert client.register_on_connect.call_count == 1
    assert entry.state == ENTRY_STATE_LOADED

    await hass.config_entries.async_unload(entry.entry_id)

    assert client.disconnect.call_count == 1
    assert client.register_on_initialized.return_value.call_count == 1
    assert client.register_on_disconnect.return_value.call_count == 1
    assert client.register_on_connect.return_value.call_count == 1
    assert entry.state == ENTRY_STATE_NOT_LOADED


async def test_home_assistant_stop(hass, client, integration):
    """Test we clean up on home assistant stop."""
    await hass.async_stop()

    assert client.disconnect.call_count == 1


async def test_on_connect_disconnect(hass, client, multisensor_6, integration):
    """Test we handle disconnect and reconnect."""
    on_connect = client.register_on_connect.call_args[0][0]
    on_disconnect = client.register_on_disconnect.call_args[0][0]
    state = hass.states.get(AIR_TEMPERATURE_SENSOR)

    assert state
    assert state.state != STATE_UNAVAILABLE

    client.connected = False

    await on_disconnect()
    await hass.async_block_till_done()

    state = hass.states.get(AIR_TEMPERATURE_SENSOR)

    assert state
    assert state.state == STATE_UNAVAILABLE

    client.connected = True

    await on_connect()
    await hass.async_block_till_done()

    state = hass.states.get(AIR_TEMPERATURE_SENSOR)

    assert state
    assert state.state != STATE_UNAVAILABLE
