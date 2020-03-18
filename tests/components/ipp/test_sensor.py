"""Tests for the IPP sensor platform."""
from homeassistant.const import ATTR_ICON, ATTR_UNIT_OF_MEASUREMENT
from homeassistant.core import HomeAssistant

from tests.components.ipp import init_integration
from tests.test_util.aiohttp import AiohttpClientMocker


async def test_sensors(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """Test the creation and values of the IPP sensors."""
    entry = await init_integration(hass, aioclient_mock, skip_setup=True)

    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    state = hass.states.get("sensor.epson_xp_6000_series")
    assert state
    assert state.attributes.get(ATTR_ICON) == "mdi:printer"
    assert state.attributes.get(ATTR_UNIT_OF_MEASUREMENT) is None
