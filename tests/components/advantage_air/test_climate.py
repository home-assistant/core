"""Test the Advantage Air Climate Platform."""

from homeassistant.components.climate.const import HVAC_MODE_FAN_ONLY

from tests.components.advantage_air import add_mock_config, api_response_with_sensor


async def test_climate_async_setup_entry(hass, aiohttp_raw_server, aiohttp_unused_port):
    """Test climate setup without sensors."""

    port = aiohttp_unused_port()
    await aiohttp_raw_server(api_response_with_sensor, port=port)
    await add_mock_config(hass, port)

    registry = await hass.helpers.entity_registry.async_get_registry()
    state = hass.states.get("climate.testac")
    assert state
    assert state.state == HVAC_MODE_FAN_ONLY
    assert state.attributes.get("min_temp") == 16
    assert state.attributes.get("max_temp") == 32
    assert state.attributes.get("current_temperature") is None

    entry = registry.async_get("climate.testac")
    assert entry
    assert entry.unique_id == "uniqueid-ac1"

    state = hass.states.get("climate.testzone")
    assert state
    assert state.attributes.get("min_temp") == 16
    assert state.attributes.get("max_temp") == 32
    assert state.attributes.get("measuredTemp") == 25
    assert state.attributes.get("setTemp") == 24

    entry = registry.async_get("climate.testzone")
    assert entry
    assert entry.unique_id == "uniqueid-ac1-z01"
