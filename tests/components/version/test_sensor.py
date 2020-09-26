"""The test for the version sensor platform."""
from homeassistant.setup import async_setup_component

from tests.async_mock import patch

MOCK_VERSION = "10.0"


async def test_version_sensor(hass):
    """Test the Version sensor."""
    config = {"sensor": {"platform": "version"}}

    assert await async_setup_component(hass, "sensor", config)


async def test_version(hass):
    """Test the Version sensor."""
    config = {"sensor": {"platform": "version", "name": "test"}}

    with patch("homeassistant.const.__version__", MOCK_VERSION):
        assert await async_setup_component(hass, "sensor", config)
        await hass.async_block_till_done()

    state = hass.states.get("sensor.test")

    assert state.state == "10.0"
