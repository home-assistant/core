"""The tests for the london_underground platform."""
from london_tube_status import API_URL

from homeassistant.components.london_underground.const import CONF_LINE
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component

from tests.common import load_fixture
from tests.test_util.aiohttp import AiohttpClientMocker

VALID_CONFIG = {
    "sensor": {"platform": "london_underground", CONF_LINE: ["Metropolitan"]}
}


async def test_valid_state(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """Test for operational london_underground sensor with proper attributes."""
    aioclient_mock.get(
        API_URL,
        text=load_fixture("line_status.json", "london_underground"),
    )

    assert await async_setup_component(hass, "sensor", VALID_CONFIG)
    await hass.async_block_till_done()

    state = hass.states.get("sensor.metropolitan")
    assert state
    assert state.state == "Good Service"
    assert state.attributes == {
        "Description": "Nothing to report",
        "attribution": "Powered by TfL Open Data",
        "friendly_name": "Metropolitan",
        "icon": "mdi:subway",
    }
