"""SMA sensor tests."""
import logging

from homeassistant.components.sensor import DOMAIN
from homeassistant.const import UNIT_VOLT
from homeassistant.setup import async_setup_component

from tests.common import assert_setup_component

_LOGGER = logging.getLogger(__name__)
BASE_CFG = {
    "platform": "sma",
    "host": "1.1.1.1",
    "password": "",
    "custom": {"my_sensor": {"key": "1234567890123", "unit": UNIT_VOLT}},
}


async def test_sma_config(hass):
    """Test new config."""
    sensors = ["current_consumption"]

    with assert_setup_component(1):
        assert await async_setup_component(
            hass, DOMAIN, {DOMAIN: dict(BASE_CFG, sensors=sensors)}
        )

    state = hass.states.get("sensor.current_consumption")
    assert state
    assert "unit_of_measurement" in state.attributes
    assert "current_consumption" not in state.attributes

    state = hass.states.get("sensor.my_sensor")
    assert state
