"""Tests for SpeedTest sensors."""
from homeassistant.components import speedtestdotnet
from homeassistant.components.sensor import DOMAIN as SENSOR_DOMAIN
from homeassistant.components.speedtestdotnet.const import DEFAULT_NAME, SENSOR_TYPES

from . import MOCK_RESULTS, MOCK_SERVER_LIST

from tests.async_mock import patch
from tests.common import MockConfigEntry


async def test_speedtestdotnet_sensors(hass):
    """Test sensors created for speedtestdotnet integration."""
    entry = MockConfigEntry(domain=speedtestdotnet.DOMAIN, data={})
    entry.add_to_hass(hass)

    with patch("speedtest.Speedtest") as mock_api:
        mock_api.return_value.get_best_server.return_value = MOCK_SERVER_LIST[
            "Server1"
        ][0]
        mock_api.return_value.results.dict.return_value = MOCK_RESULTS

        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

        assert len(hass.states.async_entity_ids(SENSOR_DOMAIN)) == 3
        print(hass.states.async_entity_ids(SENSOR_DOMAIN))

        await hass.data[speedtestdotnet.DOMAIN].async_update()
        await hass.async_block_till_done()

        for sensor_type in SENSOR_TYPES:
            if sensor_type == "ping":
                sensor = hass.states.get(
                    f"sensor.{DEFAULT_NAME}_{SENSOR_TYPES[sensor_type][0]}"
                )
                assert sensor.state == str(MOCK_RESULTS["ping"])
            if sensor_type == "download":
                sensor = hass.states.get(
                    f"sensor.{DEFAULT_NAME}_{SENSOR_TYPES[sensor_type][0]}"
                )
                assert sensor.state == str(round(MOCK_RESULTS["download"] / 10 ** 6, 2))
            if sensor_type == "upload":
                sensor = hass.states.get(
                    f"sensor.{DEFAULT_NAME}_{SENSOR_TYPES[sensor_type][0]}"
                )
                assert sensor.state == str(round(MOCK_RESULTS["upload"] / 10 ** 6, 2))
