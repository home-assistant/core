"""The tests for the london_underground platform."""

from unittest.mock import AsyncMock, patch

from london_tube_status import API_URL

from homeassistant.components.london_underground.const import CONF_LINE, DOMAIN
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component

from tests.common import async_load_fixture
from tests.test_util.aiohttp import AiohttpClientMocker

VALID_CONFIG = {
    "sensor": {"platform": "london_underground", CONF_LINE: ["Metropolitan"]}
}


async def test_valid_state(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
) -> None:
    """Test for operational london_underground sensor with proper attributes."""
    aioclient_mock.get(
        API_URL,
        text=await async_load_fixture(hass, "line_status.json", DOMAIN),
    )

    with patch(
        "homeassistant.components.london_underground.config_flow.TubeData"
    ) as mock_tube_data:
        mock_tube_data_instance = mock_tube_data.return_value
        mock_tube_data_instance.update = AsyncMock()
        # Set up via YAML which will trigger import and set up the config entry
        assert await async_setup_component(hass, "sensor", VALID_CONFIG)
        await hass.async_block_till_done()

        # Verify the config entry was created
        entries = hass.config_entries.async_entries(DOMAIN)
        assert len(entries) == 1

        # Check the state after setup completes
        state = hass.states.get("sensor.london_underground_metropolitan")
        assert state
        assert state.state == "Good Service"
        assert state.attributes == {
            "Description": "Nothing to report",
            "attribution": "Powered by TfL Open Data",
            "friendly_name": "London Underground Metropolitan",
            "icon": "mdi:subway",
        }
