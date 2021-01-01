"""Tests for SpeedTest sensors."""
from unittest.mock import patch

from homeassistant.components import speedtestdotnet
from homeassistant.components.sensor import DOMAIN as SENSOR_DOMAIN
from homeassistant.components.speedtestdotnet.const import DEFAULT_NAME, SENSOR_TYPES

from . import MOCK_RESULTS, MOCK_SERVERS, MOCK_STATES

from tests.common import MockConfigEntry


async def test_speedtestdotnet_sensors(hass):
    """Test sensors created for speedtestdotnet integration."""
    entry = MockConfigEntry(domain=speedtestdotnet.DOMAIN, data={})
    entry.add_to_hass(hass)

    with patch("speedtest.Speedtest") as mock_api:
        mock_api.return_value.get_best_server.return_value = MOCK_SERVERS[1][0]
        mock_api.return_value.results.dict.return_value = MOCK_RESULTS

        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    assert len(hass.states.async_entity_ids(SENSOR_DOMAIN)) == 3

    for sensor_type in SENSOR_TYPES:
        sensor = hass.states.get(
            f"sensor.{DEFAULT_NAME}_{SENSOR_TYPES[sensor_type][0]}"
        )
        assert sensor.state == MOCK_STATES[sensor_type]
