"""Tests for the Wireless Sensor Tags integration setup."""

from unittest.mock import patch

from homeassistant.const import EVENT_HOMEASSISTANT_STOP
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component

CONFIG = {"wirelesstag": {"username": "foo@bar.com", "password": "secret"}}


async def test_stop_monitoring_on_homeassistant_stop(hass: HomeAssistant) -> None:
    """Test cloud push monitoring is stopped when Home Assistant stops.

    The monitoring worker runs in a non-daemon thread, so it must be stopped on
    shutdown; otherwise Home Assistant cannot exit cleanly.
    """
    with patch("homeassistant.components.wirelesstag.WirelessTags") as mock_api_class:
        mock_api = mock_api_class.return_value
        mock_api.load_tags.return_value = {}

        assert await async_setup_component(hass, "wirelesstag", CONFIG)
        await hass.async_block_till_done()

        mock_api.start_monitoring.assert_called_once()
        mock_api.stop_monitoring.assert_not_called()

        hass.bus.async_fire(EVENT_HOMEASSISTANT_STOP)
        await hass.async_block_till_done()

    mock_api.stop_monitoring.assert_called_once()
