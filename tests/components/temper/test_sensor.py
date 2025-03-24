"""The tests for the temper (USB temperature sensor) component."""

from datetime import timedelta
from unittest.mock import Mock, patch

from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component
from homeassistant.util import dt as dt_util

from tests.common import async_fire_time_changed


async def test_temperature_readback(hass: HomeAssistant) -> None:
    """Test for reading sensors."""
    mock_temper_device = Mock()
    mock_temper_device.get_temperature.return_value = 12.3

    utcnow = dt_util.utcnow()

    with patch(
        "temperusb.temper.TemperHandler.get_devices",
        return_value=[mock_temper_device],
    ):
        await async_setup_component(
            hass,
            "sensor",
            {"sensor": {"platform": "temper", "name": "mydevicename"}},
        )
        await hass.async_block_till_done()

        async_fire_time_changed(hass, utcnow + timedelta(seconds=70))
        await hass.async_block_till_done(wait_background_tasks=True)

        temperature = hass.states.get("sensor.mydevicename")
        assert temperature
        assert temperature.state == "12.3"
