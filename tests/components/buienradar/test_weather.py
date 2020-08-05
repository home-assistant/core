"""The tests for the buienradar weather component."""
from homeassistant.components.buienradar.const import (
    CONF_CAMERA,
    CONF_SENSOR,
    CONF_WEATHER,
    DOMAIN,
)
from homeassistant.const import CONF_LATITUDE, CONF_LONGITUDE, CONF_NAME

from tests.common import MockConfigEntry

TEST_CFG_DATA = {
    CONF_NAME: "volkel",
    CONF_LATITUDE: 51.65,
    CONF_LONGITUDE: 5.7,
    CONF_CAMERA: False,
    CONF_SENSOR: False,
    CONF_WEATHER: True,
}


async def test_smoke_test_setup_component(hass):
    """Smoke test for successfully set-up with default config."""
    mock_entry = MockConfigEntry(domain=DOMAIN, unique_id="TEST_ID", data=TEST_CFG_DATA)

    mock_entry.add_to_hass(hass)

    await hass.config_entries.async_setup(mock_entry.entry_id)
    await hass.async_block_till_done()

    state = hass.states.get("weather.volkel")
    assert state.state == "unknown"

    await hass.config_entries.async_unload(mock_entry.entry_id)
    await hass.async_block_till_done()
