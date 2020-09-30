"""Test the Advantage Air Climate Platform."""

from homeassistant.components.advantage_air import async_setup, async_setup_entry
from homeassistant.components.advantage_air.const import DOMAIN
from homeassistant.components.climate.const import HVAC_MODE_FAN_ONLY
from homeassistant.const import CONF_IP_ADDRESS, CONF_PORT

from tests.common import MockConfigEntry
from tests.components.advantage_air import api_response_with_sensor


async def test_climate_async_setup_entry(hass, aiohttp_raw_server, aiohttp_unused_port):
    """Test climate setup without sensors."""

    port = aiohttp_unused_port()
    await aiohttp_raw_server(api_response_with_sensor, port=port)

    entry = MockConfigEntry(
        domain=DOMAIN,
        title="test entry",
        unique_id="0123456",
        data={
            CONF_IP_ADDRESS: "127.0.0.1",
            CONF_PORT: port,
        },
    )
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    registry = await hass.helpers.entity_registry.async_get_registry()
    state = hass.states.get("climate.testac")
    assert state
    assert state.state == HVAC_MODE_FAN_ONLY
    assert state.attributes.get("min_temp") == 16
    assert state.attributes.get("max_temp") == 32
    assert state.attributes.get("current_temperature") is None

    entry = registry.async_get("climate.testac")
    assert entry
    assert entry.unique_id == "uniqueid-ac1-climate"

    state = hass.states.get("climate.testzone")
    assert state
    assert state.attributes.get("min_temp") == 16
    assert state.attributes.get("max_temp") == 32
    assert state.attributes.get("measuredTemp") == 25
    assert state.attributes.get("setTemp") == 24

    entry = registry.async_get("climate.testzone")
    assert entry
    assert entry.unique_id == "uniqueid-ac1-z01-climate"
